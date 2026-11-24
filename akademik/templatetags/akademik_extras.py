import datetime as dt
from zoneinfo import ZoneInfo

from django import template

from ..services import angka, tanggal_indonesia

register = template.Library()


@register.filter
def rupiah_nilai(value):
    return angka(value)


@register.filter
def tanggal_id(value):
    return tanggal_indonesia(value)


@register.simple_tag
def tanggal_sekarang():
    return tanggal_indonesia(dt.datetime.now(ZoneInfo('Asia/Jakarta')).date())
