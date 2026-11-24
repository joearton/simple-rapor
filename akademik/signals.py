from django.contrib.auth.signals import (
    user_logged_in,
    user_logged_out,
    user_login_failed,
)
from django.dispatch import receiver

from .audit import catat_audit


@receiver(user_logged_in)
def audit_login(sender, request, user, **kwargs):
    catat_audit(user, 'LOGIN', deskripsi='Login berhasil', request=request)


@receiver(user_logged_out)
def audit_logout(sender, request, user, **kwargs):
    if user is not None:
        catat_audit(user, 'LOGOUT', deskripsi='Logout', request=request)


@receiver(user_login_failed)
def audit_login_failed(sender, credentials, request=None, **kwargs):
    username = (credentials or {}).get('username', '')
    catat_audit(
        None, 'LOGIN', deskripsi=f'Login gagal: {username}', request=request,
    )
