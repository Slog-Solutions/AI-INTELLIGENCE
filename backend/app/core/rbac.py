from fastapi import Depends, HTTPException
from starlette.status import HTTP_403_FORBIDDEN
from .dependencies import get_current_user


def require_roles(*allowed_roles: str):
    def role_dependency(user=Depends(get_current_user)):
        if user.role.name not in allowed_roles:
            raise HTTPException(status_code=HTTP_403_FORBIDDEN, detail="Forbidden: insufficient role privileges")
        return user
    return role_dependency
