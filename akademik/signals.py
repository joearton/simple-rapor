from django.contrib.auth.signals import (
    user_logged_in,
    user_logged_out,
    user_login_failed,
)
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from .assessment_sync import (
    sinkron_formatif,
    sinkron_lm,
    sinkron_sumatif,
)
from .audit import catat_audit
from .models import FormativeScore, SummativeLM, SummativeScore


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


@receiver(post_save, sender=FormativeScore)
def simpan_formatif_ke_asesmen(sender, instance, raw=False, **kwargs):
    if raw:
        return
    sinkron_formatif(instance)


@receiver(post_delete, sender=FormativeScore)
def hapus_formatif_dari_asesmen(sender, instance, **kwargs):
    sinkron_formatif(instance, hapus=True)


@receiver(post_save, sender=SummativeLM)
def simpan_lm_ke_asesmen(sender, instance, raw=False, **kwargs):
    if raw:
        return
    sinkron_lm(instance)


@receiver(post_delete, sender=SummativeLM)
def hapus_lm_dari_asesmen(sender, instance, **kwargs):
    sinkron_lm(instance, hapus=True)


@receiver(post_save, sender=SummativeScore)
def simpan_sumatif_ke_asesmen(sender, instance, raw=False, **kwargs):
    if raw:
        return
    sinkron_sumatif(instance)


@receiver(post_delete, sender=SummativeScore)
def hapus_sumatif_dari_asesmen(sender, instance, **kwargs):
    sinkron_sumatif(instance, hapus=True)
