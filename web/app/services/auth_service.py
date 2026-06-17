from functools import wraps

from flask import flash, redirect, request, session, url_for

from ..extensions import db
from ..models import User

SESSION_USER_KEY = "user_id"


def login_user(user):
    """Start a session for the given user using Flask's signed session cookie."""
    session[SESSION_USER_KEY] = user.id
    session.permanent = False


def logout_user():
    """Clear the authenticated user from the session."""
    session.pop(SESSION_USER_KEY, None)


def get_current_user():
    """Return the authenticated User, or None if there is no valid session."""
    user_id = session.get(SESSION_USER_KEY)

    if user_id is None:
        return None

    user = db.session.get(User, user_id)

    if user is None:
        # La cuenta ya no existe (p. ej. fue eliminada): limpiamos la sesion.
        session.pop(SESSION_USER_KEY, None)

    return user


def _redirect_to_login():
    flash("Inicia sesion para acceder a esta seccion.", "error")
    return redirect(url_for("auth.login", next=request.path))


def login_required(view):
    """Decorator: redirect anonymous users to the login page."""

    @wraps(view)
    def wrapped_view(*args, **kwargs):
        if get_current_user() is None:
            return _redirect_to_login()
        return view(*args, **kwargs)

    return wrapped_view


def require_authenticated_user():
    """Blueprint before_request guard: returns a redirect when not logged in."""
    if get_current_user() is None:
        return _redirect_to_login()

    return None
