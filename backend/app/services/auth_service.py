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


class InvalidCredentials(AuthError):
    pass


class InvalidToken(AuthError):
    pass


class DuplicateEmail(AuthError):
    pass


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


def _role_from_groups(claims: dict) -> str:
    groups = set(claims.get("cognito:groups", []) or [])
    if "ADMIN" in groups:
        return "ADMIN"
    if "INSTRUCTOR" in groups:
        return "INSTRUCTOR"
    return "STUDENT"


def _attributes_from_cognito(response: dict, fallback_email: str | None = None) -> dict:
    attributes = {}
    for item in response.get("UserAttributes", []):
        attributes[item["Name"]] = item["Value"]
    sub = attributes.get("sub")
    email = attributes.get("email") or fallback_email or ""
    name = attributes.get("name") or attributes.get("email") or email
    if not sub:
        raise InvalidToken()
    return {"sub": sub, "email": email.lower(), "name": name}


def sync_cognito_user(db: Session, claims: dict) -> object:
    sub = claims.get("sub")
    email = claims.get("email")
    name = claims.get("name") or claims.get("cognito:username") or email
    if not isinstance(sub, str) or not sub or not isinstance(email, str) or not email:
        raise InvalidToken()

    user = auth_repo.get_by_cognito_sub(db, sub)
    if user is None:
        user = auth_repo.get_by_email(db, email.lower())
    if user is None:
        user = auth_repo.create_cognito_user(
            db,
            cognito_sub=sub,
            name=name,
            email=email.lower(),
            role=_role_from_groups(claims),
        )
    else:
        if user.cognito_sub != sub:
            user.cognito_sub = sub
        if name:
            user.name = name
        if email:
            user.email = email.lower()
        user.password_hash = None
        user.role = _role_from_groups(claims) if claims.get("cognito:groups") else user.role
        db.commit()
        db.refresh(user)
    return user


@lru_cache(maxsize=4)
def jwks_url() -> str:
    return (
        f"https://cognito-idp.{settings.COGNITO_REGION or settings.AWS_REGION}.amazonaws.com/"
        f"{settings.COGNITO_USER_POOL_ID}/.well-known/jwks.json"
    )


def user_from_access_token(db: Session, token: str):
    try:
        signing_keys = jwt.PyJWKClient(jwks_url(), cache_keys=True, lifespan=3600).get_signing_key_from_jwt(token)
        claims = jwt.decode(
            token,
            signing_keys.key,
            algorithms=["RS256"],
            issuer=f"https://cognito-idp.{settings.COGNITO_REGION or settings.AWS_REGION}.amazonaws.com/{settings.COGNITO_USER_POOL_ID}",
            options={"verify_aud": False, "verify_exp": True},
        )
        if claims.get("token_use") == "access":
            if claims.get("client_id") != settings.COGNITO_APP_CLIENT_ID:
                logger.warning("Cognito access token rejected reason=client_id_mismatch")
                raise InvalidToken()
        elif claims.get("token_use") == "id":
            if claims.get("aud") != settings.COGNITO_APP_CLIENT_ID:
                logger.warning("Cognito ID token rejected reason=aud_mismatch")
                raise InvalidToken()
        else:
            logger.warning("Cognito token rejected reason=token_use_missing_or_invalid")
            raise InvalidToken()

        if claims.get("token_use") == "access":
            user = sync_authenticated_user(
                db,
                token,
                fallback_email=claims.get("username")
                if isinstance(claims.get("username"), str)
                else "",
            )
        else:
            user = sync_cognito_user(db, claims)
        if not user:
            raise InvalidToken()
        return user
    except InvalidToken:
        raise
    except (jwt.PyJWTError, ValueError, TypeError, OSError, BotoCoreError, ClientError) as exc:
        logger.warning(
            "Cognito token verification failed exception_type=%s",
            type(exc).__name__,
        )
        raise InvalidToken() from exc


def register_student(db: Session, data: RegisterRequest):
    del db
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


def authenticate(db: Session, *, email: str, password: str):
    del db
    try:
        response = cognito_client().initiate_auth(
            ClientId=settings.COGNITO_APP_CLIENT_ID,
            AuthFlow="USER_PASSWORD_AUTH",
            AuthParameters={"USERNAME": email.lower(), "PASSWORD": password},
        )
        result = response.get("AuthenticationResult") or {}
        if not result.get("AccessToken"):
            raise InvalidCredentials()
        return {
            "access_token": result["AccessToken"],
            "expires_in": result.get("ExpiresIn", 3600),
        }
    except (BotoCoreError, ClientError) as exc:
        _raise_cognito_error(exc)


def sync_authenticated_user(db: Session, access_token: str, fallback_email: str) -> object:
    try:
        client = cognito_client()
        response = client.get_user(AccessToken=access_token)
        identity = _attributes_from_cognito(response, fallback_email=fallback_email)
        group_response = client.admin_list_groups_for_user(
            UserPoolId=settings.COGNITO_USER_POOL_ID,
            Username=response.get("Username") or fallback_email,
        )
        claims = {
            "sub": identity["sub"],
            "email": identity["email"],
            "name": identity["name"],
            "cognito:groups": [
                item["GroupName"] for item in group_response.get("Groups", [])
            ],
        }
        return sync_cognito_user(db, claims)
    except (BotoCoreError, ClientError) as exc:
        _raise_cognito_error(exc)


def verify_email(db: Session, email: str, code: str):
    try:
        cognito_client().confirm_sign_up(
            ClientId=settings.COGNITO_APP_CLIENT_ID,
            Username=email.lower(),
            ConfirmationCode=code,
        )
        response = cognito_client().admin_get_user(
            UserPoolId=settings.COGNITO_USER_POOL_ID,
            Username=email.lower(),
        )
        identity = _attributes_from_cognito(response, fallback_email=email)
        existing = auth_repo.get_by_cognito_sub(db, identity["sub"])
        if existing is None:
            existing = auth_repo.get_by_email(db, identity["email"])
        if existing is None:
            auth_repo.create_cognito_user(
                db,
                cognito_sub=identity["sub"],
                name=identity["name"],
                email=identity["email"],
                role="STUDENT",
            )
        else:
            existing.cognito_sub = identity["sub"]
            existing.name = identity["name"]
            existing.email = identity["email"]
            existing.password_hash = None
            db.commit()
        return {"message": "Đã xác minh email."}
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
