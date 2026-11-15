from functools import lru_cache

import boto3
import jwt
from botocore.exceptions import BotoCoreError, ClientError
from sqlalchemy.orm import Session

from app.config import settings
from app.repositories import auth_repo
from app.schemas.auth import RegisterRequest
from app.utils.logging import get_logger


logger = get_logger(__name__)


class AuthError(Exception):
    pass


class InvalidToken(AuthError):
    pass


class DuplicateEmail(AuthError):
    pass


class IdentityConflict(AuthError):
    """The Cognito subject cannot be mapped without taking over another row."""


class CognitoAuthError(AuthError):
    def __init__(self, message: str, code: str = "COGNITO_AUTH_ERROR", status_code: int = 400):
        super().__init__(message)
        self.message = message
        self.code = code
        self.status_code = status_code


def cognito_client():
    if not settings.COGNITO_USER_POOL_ID or not settings.COGNITO_APP_CLIENT_ID:
        raise CognitoAuthError(
            "Cognito authentication is not configured.",
            code="COGNITO_NOT_CONFIGURED",
            status_code=503,
        )
    return boto3.client(
        "cognito-idp",
        region_name=settings.COGNITO_REGION or settings.AWS_REGION,
    )


def _raise_cognito_error(exc):
    if isinstance(exc, ClientError):
        error = exc.response.get("Error", {})
        code = error.get("Code", "CognitoError")
        message = error.get("Message", "Cognito authentication failed.")
    else:
        code = "COGNITO_UNAVAILABLE"
        message = "Cognito authentication is unavailable."
    status_code = 400
    if code in {"NotAuthorizedException", "UserNotConfirmedException"}:
        status_code = 403 if code == "UserNotConfirmedException" else 401
    if code in {"UsernameExistsException", "AliasExistsException"}:
        status_code = 409
    raise CognitoAuthError(message, code=code, status_code=status_code) from exc




def _attributes_from_cognito(response: dict, fallback_email: str | None = None) -> dict:
    attributes = {}
    for item in response.get("UserAttributes", []):
        attributes[item["Name"]] = item["Value"]
    sub = attributes.get("sub")
    email = attributes.get("email") or fallback_email or ""
    name = attributes.get("name") or attributes.get("email") or email
    if not sub:
        raise InvalidToken()
    return {
        "sub": sub,
        "email": email.lower(),
        "name": name,
        "email_verified": attributes.get("email_verified", "").lower() == "true",
        "enabled": response.get("Enabled") is True,
        "user_status": response.get("UserStatus"),
    }


def _require_provisionable_cognito_identity(identity: dict) -> None:
    if not identity.get("email"):
        logger.warning("Cognito profile rejected reason=missing_email")
        raise InvalidToken()
    if identity.get("enabled") is not True:
        logger.warning("Cognito profile rejected reason=user_disabled")
        raise InvalidToken()
    if identity.get("user_status") != "CONFIRMED":
        logger.warning("Cognito profile rejected reason=user_status_not_confirmed")
        raise InvalidToken()
    if identity.get("email_verified") is not True:
        logger.warning("Cognito profile rejected reason=email_not_verified")
        raise InvalidToken()


def _identity_from_verified_claims(
    claims: dict, access_token: str | None = None
) -> dict:
    """Build a canonical identity after the JWT/authorizer has verified claims.

    Cognito access tokens normally omit ``email``. For a subject that has no
    database profile yet, use its signed username claim to read the attributes
    once from Cognito. Existing profiles never incur this call.
    """
    sub = claims["sub"]
    username_claim = claims.get("username") or claims.get("cognito:username")
    if not isinstance(username_claim, str) or not username_claim.strip():
        logger.warning(
            "Cognito authorizer user not found "
            "reason=missing_email_and_username_claims sub_present=true"
        )
        raise InvalidToken()
    try:
        if access_token:
            # A verified bearer token can fetch its own profile without an
            # IAM admin permission. GetUser only returns active access-token
            # users, so normalize the two fields absent from that response.
            response = cognito_client().get_user(AccessToken=access_token)
            response = {
                **response,
                "Enabled": True,
                "UserStatus": "CONFIRMED",
            }
        else:
            # API Gateway authorizer contexts do not include the raw token.
            response = cognito_client().admin_get_user(
                UserPoolId=settings.COGNITO_USER_POOL_ID,
                Username=username_claim.strip(),
            )
    except (BotoCoreError, ClientError) as exc:
        _raise_cognito_error(exc)
    identity = _attributes_from_cognito(response)
    if identity["sub"] != sub:
        logger.warning("Cognito profile rejected reason=subject_mismatch")
        raise InvalidToken()
    _require_provisionable_cognito_identity(identity)
    return identity


def ensure_cognito_profile(db: Session, identity: dict):
    """Return the exact subject's RDS profile, creating it once if absent.

    This operation deliberately never links by email and never updates an
    existing row's name, email, role, password, or Cognito subject. The retry
    after an integrity error makes concurrent first requests idempotent.
    """
    sub = identity.get("sub")
    email = identity.get("email")
    name = identity.get("name")
    if not isinstance(sub, str) or not sub.strip():
        raise InvalidToken()
    if not isinstance(email, str) or not email.strip():
        raise InvalidToken()
    sub = sub.strip()
    email = email.strip().lower()
    name = name.strip() if isinstance(name, str) and name.strip() else email

    subject_user = auth_repo.get_by_cognito_sub(db, sub)
    email_user = auth_repo.get_by_email(db, email)
    if subject_user is not None:
        if email_user is not None and email_user.id != subject_user.id:
            logger.warning(
                "Cognito identity conflict reason=email_owned_by_other_user user_id=%s",
                subject_user.id,
            )
            raise IdentityConflict()
        # RDS remains authoritative for all mutable profile data and role.
        return subject_user
    if email_user is not None:
        # A concurrent insert can commit between the subject lookup and the
        # email lookup. Accept the row only when it also has the exact subject;
        # this is identity equality, not email-based account linking.
        if email_user.cognito_sub == sub:
            return email_user
        logger.warning(
            "Cognito identity conflict reason=email_match_different_subject user_id=%s",
            email_user.id,
        )
        raise IdentityConflict()

    try:
        return auth_repo.create_cognito_user(
            db,
            cognito_sub=sub,
            name=name,
            email=email,
            # Privileged roles are never bootstrapped from Cognito claims/groups.
            role="STUDENT",
        )
    except auth_repo.EmailAlreadyExists as exc:
        # Another worker may have won the same first-login insert. Accept only
        # the exact same subject/email mapping; all other uniqueness races fail.
        subject_user = auth_repo.get_by_cognito_sub(db, sub)
        email_user = auth_repo.get_by_email(db, email)
        if (
            subject_user is not None
            and email_user is not None
            and subject_user.id == email_user.id
        ):
            return subject_user
        raise IdentityConflict() from exc


def authorizer_claims_from_event(event: object) -> dict | None:
    if not isinstance(event, dict):
        return None
    request_context = event.get("requestContext")
    if not isinstance(request_context, dict):
        return None
    authorizer = request_context.get("authorizer")
    if not isinstance(authorizer, dict):
        return None
    jwt_context = authorizer.get("jwt")
    if isinstance(jwt_context, dict):
        claims = jwt_context.get("claims")
    else:
        claims = authorizer.get("claims")
    return claims if isinstance(claims, dict) else None


def sync_authorizer_claims(db: Session, claims: dict, access_token: str | None = None) -> object:
    sub = claims.get("sub")
    if not isinstance(sub, str) or not sub:
        raise InvalidToken()

    if claims.get("token_use") != "access":
        raise InvalidToken()
    if (
        not settings.COGNITO_APP_CLIENT_ID
        or claims.get("client_id") != settings.COGNITO_APP_CLIENT_ID
    ):
        raise InvalidToken()

    expected_issuer = (
        f"https://cognito-idp.{settings.COGNITO_REGION or settings.AWS_REGION}.amazonaws.com/"
        f"{settings.COGNITO_USER_POOL_ID}"
    )
    if claims.get("iss") != expected_issuer or not settings.COGNITO_USER_POOL_ID:
        raise InvalidToken()

    user = auth_repo.get_by_cognito_sub(db, sub)
    if user is None:
        try:
            user = ensure_cognito_profile(
                db,
                _identity_from_verified_claims(claims, access_token=access_token),
            )
        except IdentityConflict as exc:
            raise InvalidToken() from exc
    # Existing rows are intentionally read-only here. users.role is
    # authoritative, and stale Cognito groups/profile claims cannot undo an
    # administrator's changes or overwrite local credentials.
    return user


@lru_cache(maxsize=4)
def jwks_url() -> str:
    return (
        f"https://cognito-idp.{settings.COGNITO_REGION or settings.AWS_REGION}.amazonaws.com/"
        f"{settings.COGNITO_USER_POOL_ID}/.well-known/jwks.json"
    )


def user_from_access_token(db: Session, token: str):
    # Untrusted header only selects a verifier. Each verifier pins its own
    # algorithm, key and issuer; a failed verification never falls back.
    try:
        local_token = jwt.get_unverified_header(token).get("alg") == "HS256"
    except jwt.PyJWTError:
        local_token = False
    if local_token:
        from app.services import local_auth_service
        return local_auth_service.user_from_access_token(db, token)
    try:
        signing_keys = jwt.PyJWKClient(jwks_url(), cache_keys=True, lifespan=3600).get_signing_key_from_jwt(token)
        claims = jwt.decode(
            token,
            signing_keys.key,
            algorithms=["RS256"],
            issuer=f"https://cognito-idp.{settings.COGNITO_REGION or settings.AWS_REGION}.amazonaws.com/{settings.COGNITO_USER_POOL_ID}",
            options={"verify_aud": False, "verify_exp": True},
        )
        if claims.get("token_use") != "access":
            logger.warning("Cognito token rejected reason=token_use_missing_or_invalid")
            raise InvalidToken()
        if claims.get("client_id") != settings.COGNITO_APP_CLIENT_ID:
            logger.warning("Cognito access token rejected reason=client_id_mismatch")
            raise InvalidToken()

        user = sync_authorizer_claims(db, claims, access_token=token)
        if not user:
            raise InvalidToken()
        return user
    except InvalidToken:
        raise
    except (jwt.PyJWTError, ValueError, TypeError, OSError, BotoCoreError, ClientError,
            auth_repo.EmailAlreadyExists) as exc:
        logger.warning(
            "Cognito token verification failed exception_type=%s",
            type(exc).__name__,
        )
        raise InvalidToken() from exc


def register_student(db: Session, data: RegisterRequest):
    if auth_repo.get_by_email(db, str(data.email)) is not None:
        raise CognitoAuthError("Email is already registered. Use its original sign-in method.",
                               code="EMAIL_EXISTS", status_code=409)
    try:
        response = cognito_client().sign_up(
            ClientId=settings.COGNITO_APP_CLIENT_ID,
            Username=str(data.email).lower(),
            Password=data.password,
            UserAttributes=[
                {"Name": "email", "Value": str(data.email).lower()},
                {"Name": "name", "Value": data.name.strip()},
            ],
        )
        return {
            "verification_required": response.get("UserConfirmed") is False
            or bool(response.get("CodeDeliveryDetails")),
            "message": "Mã xác minh đã được gửi.",
            "retry_after": 60,
        }
    except (BotoCoreError, ClientError) as exc:
        _raise_cognito_error(exc)


def verify_email(db: Session, email: str, code: str):
    try:
        client = cognito_client()
        try:
            client.confirm_sign_up(
                ClientId=settings.COGNITO_APP_CLIENT_ID,
                Username=email.lower(),
                ConfirmationCode=code,
            )
        except ClientError as confirm_error:
            # Confirmation can succeed while the following database write
            # fails. A retry must repair that partial success, but only after a
            # read confirms Cognito is already in the expected final state.
            error_code = confirm_error.response.get("Error", {}).get("Code")
            if error_code != "NotAuthorizedException":
                raise
            response = client.admin_get_user(
                UserPoolId=settings.COGNITO_USER_POOL_ID,
                Username=email.lower(),
            )
            if response.get("UserStatus") != "CONFIRMED":
                raise confirm_error
        else:
            response = client.admin_get_user(
                UserPoolId=settings.COGNITO_USER_POOL_ID,
                Username=email.lower(),
            )
        identity = _attributes_from_cognito(response, fallback_email=email)
        _require_provisionable_cognito_identity(identity)
        try:
            ensure_cognito_profile(db, identity)
        except IdentityConflict as exc:
            raise CognitoAuthError(
                "Email belongs to a different identity. Account linking is not supported.",
                code="IDENTITY_CONFLICT",
                status_code=409,
            ) from exc
        return {"message": "Đã xác minh email."}
    except InvalidToken as exc:
        raise CognitoAuthError(
            "Cognito returned an incomplete identity profile.",
            code="COGNITO_PROFILE_INVALID",
            status_code=502,
        ) from exc
    except (BotoCoreError, ClientError) as exc:
        _raise_cognito_error(exc)


def resend_verification(email: str):
    try:
        cognito_client().resend_confirmation_code(
            ClientId=settings.COGNITO_APP_CLIENT_ID,
            Username=email.lower(),
        )
        return {"message": "Mã xác minh mới đã được gửi.", "retry_after": 60}
    except (BotoCoreError, ClientError) as exc:
        _raise_cognito_error(exc)


def forgot_password(email: str):
    try:
        cognito_client().forgot_password(
            ClientId=settings.COGNITO_APP_CLIENT_ID,
            Username=email.lower(),
        )
        return {"message": "Nếu email phù hợp, mã đặt lại đã được gửi.", "retry_after": 60}
    except (BotoCoreError, ClientError) as exc:
        if isinstance(exc, ClientError):
            code = exc.response.get("Error", {}).get("Code")
            if code == "UserNotFoundException":
                return {
                    "message": "Nếu email phù hợp, mã đặt lại đã được gửi.",
                    "retry_after": 60,
                }
        _raise_cognito_error(exc)


def reset_password(email: str, code: str, password: str):
    try:
        cognito_client().confirm_forgot_password(
            ClientId=settings.COGNITO_APP_CLIENT_ID,
            Username=email.lower(),
            ConfirmationCode=code,
            Password=password,
        )
        return {"message": "Đã đặt lại mật khẩu."}
    except (BotoCoreError, ClientError) as exc:
        _raise_cognito_error(exc)


def change_password(access_token: str, current_password: str, new_password: str):
    try:
        cognito_client().change_password(
            AccessToken=access_token,
            PreviousPassword=current_password,
            ProposedPassword=new_password,
        )
        return {"message": "Password changed successfully"}
    except (BotoCoreError, ClientError) as exc:
        _raise_cognito_error(exc)


def admin_create_user(*, name: str, email: str, password: str, role: str) -> str:
    try:
        client = cognito_client()
        response = client.admin_create_user(
            UserPoolId=settings.COGNITO_USER_POOL_ID,
            Username=email.lower(),
            TemporaryPassword=password,
            MessageAction="SUPPRESS",
            UserAttributes=[
                {"Name": "email", "Value": email.lower()},
                {"Name": "email_verified", "Value": "true"},
                {"Name": "name", "Value": name.strip()},
            ],
        )
        sub = next(
            (
                item["Value"]
                for item in response.get("User", {}).get("Attributes", [])
                if item["Name"] == "sub"
            ),
            None,
        )
        if sub is None:
            response = client.admin_get_user(
                UserPoolId=settings.COGNITO_USER_POOL_ID,
                Username=email.lower(),
            )
            sub = next(
                (item["Value"] for item in response.get("UserAttributes", []) if item["Name"] == "sub"),
                None,
            )
        if not sub:
            raise CognitoAuthError("Cognito did not return the new user's sub.", code="COGNITO_USER_SUB_MISSING")
        client.admin_set_user_password(
            UserPoolId=settings.COGNITO_USER_POOL_ID,
            Username=email.lower(),
            Password=password,
            Permanent=True,
        )
        client.admin_add_user_to_group(
            UserPoolId=settings.COGNITO_USER_POOL_ID,
            Username=email.lower(),
            GroupName=role,
        )
        return sub
    except (BotoCoreError, ClientError) as exc:
        _raise_cognito_error(exc)


def admin_update_role(*, cognito_sub: str, email: str, old_role: str, new_role: str):
    try:
        client = cognito_client()
        username = email.lower()
        if old_role != new_role:
            if old_role in {"STUDENT", "INSTRUCTOR", "ADMIN"}:
                try:
                    client.admin_remove_user_from_group(
                        UserPoolId=settings.COGNITO_USER_POOL_ID,
                        Username=username,
                        GroupName=old_role,
                    )
                except ClientError as exc:
                    if exc.response.get("Error", {}).get("Code") != "ResourceNotFoundException":
                        raise
            client.admin_add_user_to_group(
                UserPoolId=settings.COGNITO_USER_POOL_ID,
                Username=username,
                GroupName=new_role,
            )
    except (BotoCoreError, ClientError) as exc:
        _raise_cognito_error(exc)


def admin_update_profile(*, cognito_sub: str, email: str, name: str | None = None, new_email: str | None = None):
    try:
        attributes = []
        if name is not None:
            attributes.append({"Name": "name", "Value": name.strip()})
        if new_email is not None:
            attributes.append({"Name": "email", "Value": new_email.lower()})
            attributes.append({"Name": "email_verified", "Value": "true"})
        if attributes:
            cognito_client().admin_update_user_attributes(
                UserPoolId=settings.COGNITO_USER_POOL_ID,
                Username=email.lower(),
                UserAttributes=attributes,
            )
    except (BotoCoreError, ClientError) as exc:
        _raise_cognito_error(exc)


def admin_set_user_enabled(*, cognito_sub: str, enabled: bool):
    """Enable or disable the Cognito identity linked to the database user."""
    try:
        client = cognito_client()
        params = {
            "UserPoolId": settings.COGNITO_USER_POOL_ID,
            "Username": cognito_sub,
        }
        if enabled:
            client.admin_enable_user(**params)
        else:
            client.admin_disable_user(**params)
    except (BotoCoreError, ClientError) as exc:
        _raise_cognito_error(exc)
