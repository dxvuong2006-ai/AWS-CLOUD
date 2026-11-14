from functools import lru_cache

import boto3
import jwt
from botocore.exceptions import BotoCoreError, ClientError
from sqlalchemy.orm import Session

from app.config import settings
from app.repositories import auth_repo
from app.schemas.auth import RegisterRequest
from app.utils.logging import get_logger
import json


logger = get_logger(__name__)


class AuthError(Exception):
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
    raw = claims.get("cognito:groups") or []

    if isinstance(raw, str):
        raw = raw.strip()

        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            parsed = raw.strip("[]").split(",")

        raw = parsed

    if isinstance(raw, str):
        raw = [raw]

    if not isinstance(raw, (list, tuple, set)):
        raw = []

    groups = {
        group.strip().strip('"\'').upper()
        for group in raw
        if isinstance(group, str)
    }

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

    # Chỉ lấy hồ sơ bằng token đã xác thực; GetUser không cần IAM admin.
    if auth_repo.get_by_cognito_sub(db, sub) is None:
        if not access_token:
            raise CognitoAuthError(
                "Cần Access Token để tạo hồ sơ người dùng.",
                code="PROFILE_TOKEN_REQUIRED", status_code=401,
            )
        try:
            response = cognito_client().get_user(AccessToken=access_token)
        except (BotoCoreError, ClientError) as exc:
            _raise_cognito_error(exc)
        attributes = {
            item["Name"]: item["Value"]
            for item in response.get("UserAttributes", [])
        }
        if attributes.get("sub") != sub:
            raise InvalidToken()
        if attributes.get("email_verified") != "true" or not attributes.get("email"):
            raise CognitoAuthError(
                "Email chưa được xác minh.", code="EMAIL_NOT_VERIFIED", status_code=403,
            )
        claims = {**claims, "email": attributes["email"], "name": attributes.get("name")}

    email_claim = claims.get("email")
    email = (
        email_claim.strip().lower()
        if isinstance(email_claim, str) and email_claim.strip()
        else None
    )
    name_claim = claims.get("name")
    name = (
        name_claim.strip()
        if isinstance(name_claim, str) and name_claim.strip()
        else None
    )

    user = auth_repo.get_by_cognito_sub(db, sub)
    if user is None and email:
        user = auth_repo.get_by_email(db, email)

    if user is None:
        if not email:
            logger.warning("Cognito authorizer user not found reason=missing_email_claim sub_present=true")
            raise InvalidToken()
        user = auth_repo.create_cognito_user(
            db,
            cognito_sub=sub,
            name=name or email,
            email=email,
            role="INSTRUCTOR" if email in {"dxvuong@gmail.com", "dxvuong2006@gmail.com"} else "STUDENT",
        )
    else:
        if user.cognito_sub and user.cognito_sub != sub and not user.cognito_sub.startswith("local:"):
            raise CognitoAuthError(
                "Email đã liên kết với tài khoản khác.",
                code="ACCOUNT_LINK_CONFLICT", status_code=409,
            )
        if user.cognito_sub != sub:
            user.cognito_sub = sub
        if email:
            user.email = email
        if name:
            user.name = name
        user.password_hash = None
        logger.info(
        "Cognito groups diagnostic: type=%s, raw=%r",
        type(claims.get("cognito:groups")).__name__,
        claims.get("cognito:groups"),)
        if "cognito:groups" in claims:
            user.role = _role_from_groups(claims)
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


def verify_email(db: Session, email: str, code: str):
    try:
        client = cognito_client()
        client.confirm_sign_up(
            ClientId=settings.COGNITO_APP_CLIENT_ID,
            Username=email.lower(),
            ConfirmationCode=code,
        )
        # Hồ sơ database được tạo khi đăng nhập bằng token hợp lệ.
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
