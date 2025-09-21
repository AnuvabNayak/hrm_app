import os
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv
from jose import JWTError, jwt
from jose.exceptions import ExpiredSignatureError
import bcrypt
from fastapi import HTTPException, status

# Load env variables
load_dotenv()

SECRET_KEY = os.getenv("SECRET_KEY")
if not SECRET_KEY:
    raise RuntimeError("SECRET_KEY environment variable not set")

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 12 * 60

def hash_password(password: str) -> str:
    # Hash a plaintext password using bcrypt.
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

def verify_password(plain_password: str, hashed_password: str) -> bool:
    # Verify a plaintext password against a hashed password.
    return bcrypt.checkpw(plain_password.encode('utf-8'), hashed_password.encode('utf-8'))

def create_access_token(data: dict, expires_delta: timedelta | None = None):
    to_encode = data.copy()
    now = datetime.utcnow()
    expire = now + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire, "iat": now, "nbf": now})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

def decode_access_token(token: str):
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except ExpiredSignatureError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token expired")
    except JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

# import os
# from datetime import datetime, timedelta

# from dotenv import load_dotenv
# from jose import JWTError, jwt
# import bcrypt
# from fastapi import HTTPException, status

# #Load env variables
# load_dotenv()
# SECRET_KEY = os.getenv("SECRET_KEY")
# if not SECRET_KEY:
#     raise RuntimeError("SECRET_KEY environment variable not set")

# ALGORITHM = "HS256"
# ACCESS_TOKEN_EXPIRE_MINUTES = 30

# def hash_password(password: str) -> str:
#     #Hash a plaintext password using bcrypt.
#     return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

# def verify_password(plain_password: str, hashed_password: str) -> bool:
#     # Verify a plaintext password against a hashed password.
#     return bcrypt.checkpw(plain_password.encode('utf-8'), hashed_password.encode('utf-8'))

# def create_access_token(data: dict, expires_delta: timedelta = None):
#     # Create a JWT access token.
#     to_encode = data.copy()
#     expire = datetime.utcnow() + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
#     to_encode.update({"exp": expire})
#     encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
#     return encoded_jwt

# def decode_access_token(token: str):
#     # Decode a JWT access token and return the payload.
#     try:
#         payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
#         return payload
#     except JWTError:
#         raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")