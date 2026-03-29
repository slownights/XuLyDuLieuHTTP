from fastapi import FastAPI, HTTPException, Request, Response, status, Depends, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.security import OAuth2PasswordRequestForm
from fastapi.templating import Jinja2Templates
from starlette.exceptions import HTTPException as StarletteHTTPException
from sqlalchemy import select, func
from sqlalchemy.orm import Session
from typing import Annotated
from datetime import timedelta
from PIL import UnidentifiedImageError
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
import bleach
import sqlite3

import models
from database import Base, engine,get_db
from schemas import UserCreate, UserPublic, UserPrivate, UserUpdate, Token
from auth import create_access_token, hash_password, verify_password, CurrentUser
from config import settings
from image import delete_profile_image, process_profile_image, process_profile_image_unsafe

limiter = Limiter(key_func=get_remote_address)
templates = Jinja2Templates(directory="templates")
Base.metadata.create_all(bind=engine)

app = FastAPI()
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.mount("/media", StaticFiles(directory="media"), name="media")


# HTML FRONTEND ENDPOINTS
# HOME/LOGIN PAGE
@app.get("/", include_in_schema=False, name="home")
@app.get("/login", include_in_schema=False, name="login")
def login_page(request: Request):
    return templates.TemplateResponse(
        request,
        "login.html",
        {"title": "Login"}
    )


# REGISTER PAGE
@app.get("/register", include_in_schema=False, name="register")
def register_page(request: Request):
    return templates.TemplateResponse(
        request,
        "register.html",
        {"title": "Register"}
    )


# PERSONAL ACCOUNT INFORMATION PAGE
@app.get("/account", include_in_schema=False, name="account")
def account_page(request: Request):
    return templates.TemplateResponse(
        request,
        "account.html",
        {"title": "Account"}
    )


# PUBLIC ACCOUNT INFORMATION PAGE
@app.get("/users/{user_id}", include_in_schema=False, name="public_profile")
def account_page(request: Request):
    return templates.TemplateResponse(
        request,
        "public_profile.html",
        {"title": "Profile"}
    )


# API BACKEND ENDPOINTS
# CREATE USER ACCOUNT
@app.post(
    "/api/users/", 
    response_model=UserPrivate, 
    status_code=status.HTTP_201_CREATED
)
def create_user(user: UserCreate, db: Annotated[Session, Depends(get_db)]):
    clean_username = bleach.clean(user.username.strip()).lower()
    clean_full_name = bleach.clean(user.full_name.strip())
    # # STORED XSS
    # clean_full_name = user.full_name
    clean_email = user.email.strip().lower()

    result = db.execute(
        select(models.User).
        where(func.lower(models.User.username) == clean_username)
    )
    existing_user = result.scalars().first()

    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already exists"
        )
    
    result = db.execute(
        select(models.User).
        where(models.User.email == clean_email)
    )
    existing_email = result.scalars().first()

    if existing_email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already exists",
        )
    
    new_user = models.User(
        username = clean_username,
        full_name = clean_full_name,
        email = clean_email,
        password_hash = hash_password(user.password)
    )

    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    return new_user


# USER ACCOUNT LOG IN
@app.post(
    "/api/users/token",
    response_model=Token
)
def login_for_access_token(
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    db: Annotated[Session, Depends(get_db)]
):
    result = db.execute(
        select(models.User).
        where(models.User.username == form_data.username.lower())
    )
    user = result.scalars().first()

    if not user or not verify_password(form_data.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"}
        )
    
    access_token_expires = timedelta(minutes=settings.access_token_expire_minutes)
    access_token = create_access_token(
        data={"sub": str(user.id)},
        expires_delta=access_token_expires
    )

    return Token(access_token=access_token, token_type="bearer")


# GET LOGGED IN USER INFORMATION
@app.get(
    "/api/users/account",
    response_model=UserPrivate
)
def get_current_user(current_user: CurrentUser):
    return current_user
    

# GET PUBLIC USER INFORMATION
@app.get(
    "/api/users/{user_id}",
    response_model=UserPublic
)
def get_user(
    user_id: int, 
    db: Annotated[Session, Depends(get_db)]
):
    result = db.execute(
        select(models.User).
        where(models.User.id == user_id)
    )
    user = result.scalars().first()

    if user:
        return user
    
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="User not found"
    )


# # [SQL INJECTION]
# # PUBLIC USER ENDPOINT FOR SQL INJECTION 
# @app.get("/api/users/{user_id}")
# def get_user_unsafe(user_id):
#     conn = sqlite3.connect("database.db")
#     cursor = conn.cursor()

#     query = f"SELECT id, username, full_name, image_file, date_joined FROM users WHERE id = '{user_id}'"

#     try:
#         cursor.execute(query)
#         user = cursor.fetchone()
#         conn.close()

#         if user:
#             image_file = user[3]
#             image_path = f"/media/profile_pics/{image_file}" if image_file else "/media/profile_pics/default.jpg"
            
#             return {
#                 "id": user[0], 
#                 "username": user[1], 
#                 "full_name": user[2],
#                 "image_path": image_path,
#                 "date_joined": user[4]
#             }
        
#         raise HTTPException(
#             status_code=status.HTTP_404_NOT_FOUND,
#             detail="User not found"
#         )
#     except sqlite3.Error as e:
#         raise HTTPException(
#             status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
#             detail="Database error"
#         )


# UPDATE USER INFORMATION
@app.patch(
    "/api/users/{user_id}",
    response_model=UserPrivate
)
def update_user(
    user_id: int,
    user_update: UserUpdate,
    current_user: CurrentUser,
    db: Annotated[Session, Depends(get_db)]
):
    if user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorised to update this user"
        )

    result = db.execute(
        select(models.User).
        where(models.User.id == user_id)
    )
    user = result.scalars().first()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    
    if user_update.username is not None:
        clean_username = bleach.clean(user_update.username.strip(), strip=True).lower()

        if not clean_username:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, 
                detail="Invalid name content"
            )
        
        if clean_username != user.username:
            result = db.execute(
                select(models.User).where(models.User.username == clean_username)
            )
            existing_user = result.scalars().first()

            if existing_user:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Username already exists"
                )
        user.username = clean_username

    if user_update.email is not None:
        clean_email = user_update.email.strip().lower()
        
        if clean_email != user.email:
            result = db.execute(
                select(models.User).where(models.User.email == clean_email)
            )
            existing_email = result.scalars().first()

            if existing_email:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Email already registered"
                )
        user.email = clean_email

    if user_update.full_name is not None:
        # clean_full_name = bleach.clean(user_update.full_name.strip(), strip=True)
        clean_full_name = user_update.full_name
        
        if not clean_full_name:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, 
                detail="Invalid name content"
            )
        user.full_name = clean_full_name

    db.commit()
    db.refresh(user)

    return user


# DELETE USER
@app.delete(
    "/api/users/{user_id}", 
    status_code=status.HTTP_204_NO_CONTENT
)
def delete_user(
    user_id: int, 
    current_user: CurrentUser, 
    db: Annotated[Session, Depends(get_db)]
):
    if user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorised to delete this user"
        )
    
    result = db.execute(
        select(models.User).
        where(models.User.id == user_id)
    )
    user = result.scalars().first()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    old_filename = user.image_file
    
    db.delete(user)
    db.commit()

    if old_filename:
        delete_profile_image(old_filename)


# UPLOAD PROFILE PICTURE
@app.patch(
    "/api/users/{user_id}/picture", 
    response_model=UserPrivate
)
def upload_profile_picture(
    user_id: int,
    file: UploadFile,
    current_user: CurrentUser,
    db: Annotated[Session, Depends(get_db)],
):
    if current_user.id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to update this user's picture",
        )

    content = file.file.read()
    
    if len(content) > settings.max_upload_size:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File too large. Maximum size is {settings.max_upload_size // (1024 * 1024)}MB",
        )

    try:
        new_filename = process_profile_image(content)
    except UnidentifiedImageError as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid image file",
        ) from error

    # # [PATH TRAVERSAL]
    # new_filename = process_profile_image_unsafe(content, file.filename)

    old_filename = current_user.image_file
    current_user.image_file = new_filename

    db.commit()
    db.refresh(current_user)

    if old_filename:
        delete_profile_image(old_filename)

    return current_user


# FRONTEND ERROR PAGE
@app.exception_handler(StarletteHTTPException)
def general_http_exception_handler(request: Request, exception: StarletteHTTPException):
    message = (
        exception.detail
        if exception.detail
        else "An error occured. Check your request again."
    )

    if request.url.path.startswith("/api"):
        return JSONResponse(
            status_code=exception.status_code,
            content={"detail": message},
        )
    
    return templates.TemplateResponse(
        request,
        "error.html",
        {
            "status_code": exception.status_code,
            "title": exception.status_code,
            "message": message
        },
        status_code=exception.status_code,
    )


# FRONTEND VALIDATION ERROR PAGE
@app.exception_handler(RequestValidationError)
def validation_exception_handler(request: Request, exception: RequestValidationError):
    if request.url.path.startswith("/api"):
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            content={"detail": exception.errors()},
        )

    return templates.TemplateResponse(
        request,
        "error.html",
        {
            "status_code": status.HTTP_422_UNPROCESSABLE_CONTENT,
            "title": status.HTTP_422_UNPROCESSABLE_CONTENT,
            "message": "Invalid request. Check your input again.",
        },
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
    )