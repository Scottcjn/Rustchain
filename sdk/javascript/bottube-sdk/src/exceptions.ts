/**
 * BoTTube SDK Exceptions
 */

export class BoTTubeError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "BoTTubeError";
  }
}

export class AuthenticationError extends BoTTubeError {
  constructor(message: string) {
    super(message);
    this.name = "AuthenticationError";
  }
}

export class APIError extends BoTTubeError {
  statusCode?: number;
  endpoint?: string;

  constructor(message: string, statusCode?: number, endpoint?: string) {
    super(message);
    this.name = "APIError";
    this.statusCode = statusCode;
    this.endpoint = endpoint;
  }
}

export class UploadError extends BoTTubeError {
  validationErrors?: string[];

  constructor(message: string, validationErrors?: string[]) {
    super(message);
    this.name = "UploadError";
    this.validationErrors = validationErrors || [];
  }
}
