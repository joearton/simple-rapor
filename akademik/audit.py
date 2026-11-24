from .models import AuditLog


def catat_audit(user, aksi, obj=None, deskripsi='', request=None, data_lama=None, data_baru=None):
    if obj is not None:
        model = obj.__class__.__name__
        object_id = str(getattr(obj, 'pk', '') or '')
    else:
        model = ''
        object_id = ''
    ip = None
    user_agent = ''
    if request is not None:
        ip = (
            request.META.get('HTTP_X_FORWARDED_FOR', '').split(',')[0].strip()
            or request.META.get('REMOTE_ADDR')
        )
        user_agent = request.META.get('HTTP_USER_AGENT', '')[:250]
    return AuditLog.objects.create(
        user=user if getattr(user, 'is_authenticated', False) else None,
        aksi=aksi,
        model=model,
        object_id=object_id,
        deskripsi=deskripsi,
        data_lama=data_lama,
        data_baru=data_baru,
        ip=ip,
        user_agent=user_agent,
    )
