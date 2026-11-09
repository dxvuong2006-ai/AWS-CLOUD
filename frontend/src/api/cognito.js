import { Amplify } from "aws-amplify";
import {
  fetchAuthSession,
  signIn,
  signOut,
} from "aws-amplify/auth";
import { cognitoUserPoolsTokenProvider } from "aws-amplify/auth/cognito";
import { sessionStorage as amplifySessionStorage } from "aws-amplify/utils";
import { readSession, writeSession } from "./session";

const region = import.meta.env.VITE_AWS_REGION || import.meta.env.VITE_COGNITO_REGION;
const userPoolId = import.meta.env.VITE_COGNITO_USER_POOL_ID;
const userPoolClientId = import.meta.env.VITE_COGNITO_APP_CLIENT_ID;
const isConfigured = Boolean(region && userPoolId && userPoolClientId);

class CognitoAuthError extends Error {
  constructor(status, message, code = "") {
    super(message);
    this.status = status;
    this.code = code;
  }
}

if (isConfigured) {
  Amplify.configure({
    Auth: {
      Cognito: {
        userPoolId,
        userPoolClientId,
      },
    },
  });
  cognitoUserPoolsTokenProvider.setKeyValueStorage(amplifySessionStorage);
}

function requireConfiguration() {
  if (!isConfigured) {
    throw new CognitoAuthError(
      503,
      "Cognito chưa được cấu hình. Hãy kiểm tra VITE_AWS_REGION, VITE_COGNITO_REGION, VITE_COGNITO_USER_POOL_ID và VITE_COGNITO_APP_CLIENT_ID.",
      "COGNITO_NOT_CONFIGURED",
    );
  }
}

function sessionFromTokens(tokens) {
  const accessToken = tokens?.accessToken;
  const expiresAt = accessToken?.payload?.exp;
  if (!accessToken || !Number.isFinite(expiresAt)) return null;
  return {
    token: accessToken.toString(),
    expiresAt: expiresAt * 1000,
  };
}

export async function currentCognitoSession(forceRefresh = false) {
  if (!isConfigured) return null;
  const { tokens } = await fetchAuthSession({ forceRefresh });
  return sessionFromTokens(tokens);
}

export async function currentCognitoAccessToken() {
  const session = await currentCognitoSession();
  if (!session) return null;
  writeSession({ ...session, user: readSession()?.user ?? null });
  return session.token;
}

export async function refreshCognitoSession() {
  return currentCognitoSession(true);
}

export async function signInWithCognito(email, password) {
  requireConfiguration();
  try {
    const result = await signIn({
      username: email,
      password,
      options: { authFlowType: "USER_PASSWORD_AUTH" },
    });
    if (!result.isSignedIn) {
      const step = result.nextStep?.signInStep || "SIGN_IN_INCOMPLETE";
      const messages = {
        CONFIRM_SIGN_UP: "Email chưa được xác minh. Vui lòng xác minh trước khi đăng nhập.",
        RESET_PASSWORD: "Tài khoản cần đặt lại mật khẩu trước khi đăng nhập.",
        CONFIRM_SIGN_IN_WITH_NEW_PASSWORD_REQUIRED: "Tài khoản cần đổi mật khẩu tạm thời trước khi đăng nhập.",
        CONFIRM_SIGN_IN_WITH_TOTP_CODE: "Tài khoản yêu cầu mã xác minh MFA; luồng này chưa có màn hình nhập mã.",
        CONFIRM_SIGN_IN_WITH_SMS_CODE: "Tài khoản yêu cầu mã SMS MFA; luồng này chưa có màn hình nhập mã.",
        CONFIRM_SIGN_IN_WITH_EMAIL_CODE: "Tài khoản yêu cầu mã email MFA; luồng này chưa có màn hình nhập mã.",
      };
      throw new CognitoAuthError(
        409,
        messages[step] || "Cognito yêu cầu bước xác minh bổ sung trước khi đăng nhập.",
        step,
      );
    }

    const session = sessionFromTokens((await fetchAuthSession()).tokens);
    if (!session) {
      throw new CognitoAuthError(503, "Cognito không trả về Access Token hợp lệ.", "COGNITO_TOKEN_MISSING");
    }
    return {
      access_token: session.token,
      expires_in: Math.max(0, Math.floor((session.expiresAt - Date.now()) / 1000)),
    };
  } catch (error) {
    if (error instanceof CognitoAuthError) throw error;
    const code = error?.name || "COGNITO_AUTH_ERROR";
    const status = {
      UserNotConfirmedException: 403,
      PasswordResetRequiredException: 409,
      NotAuthorizedException: 401,
      UserNotFoundException: 401,
      LimitExceededException: 429,
      TooManyRequestsException: 429,
      ResourceNotFoundException: 400,
      InvalidParameterException: 400,
    }[code] || 503;
    throw new CognitoAuthError(status, error?.message || "Không thể đăng nhập bằng Cognito.", code);
  }
}

export async function signOutFromCognito() {
  if (isConfigured) await signOut();
}
