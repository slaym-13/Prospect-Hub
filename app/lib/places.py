"""Google Places API (New) - Place Details. It returns website and phone, never an email address."""
import os
from urllib.parse import quote

import requests

from .util import ApiError, now_iso

FIELDS = 'id,displayName,websiteUri,nationalPhoneNumber,internationalPhoneNumber,businessStatus,rating,userRatingCount,googleMapsUri'


def BASE():
    return os.environ.get('PLACES_BASE_URL') or 'https://places.googleapis.com'


def place_details(place_id, api_key):
    r = requests.get(f"{BASE()}/v1/places/{quote(place_id, safe='')}",
                     headers={'X-Goog-Api-Key': api_key, 'X-Goog-FieldMask': FIELDS}, timeout=20)
    if not r.ok:
        msg = f'Places API HTTP {r.status_code}'
        try:
            m = (r.json().get('error') or {}).get('message')
            if m:
                msg += ': ' + m
        except ValueError:
            pass
        raise ApiError(msg, status=r.status_code)
    j = r.json()
    return {'website': j.get('websiteUri') or '', 'phone': j.get('nationalPhoneNumber') or '',
            'intlPhone': j.get('internationalPhoneNumber') or '', 'status': j.get('businessStatus') or '',
            'rating': j.get('rating'), 'reviews': j.get('userRatingCount'), 'maps': j.get('googleMapsUri') or ''}


def apply_details(lead, d):
    """Copy useful facts onto the lead. Never overwrites something already filled in."""
    changes = []
    if not lead.get('site_web') and d['website']:
        lead['site_web'] = d['website']
        changes.append('website')
    if not lead.get('telephone') and d['phone']:
        lead['telephone'] = d['phone']
        changes.append('phone')
    if d['status']:
        lead['placesStatus'] = d['status']
    if d['rating'] is not None and lead.get('note') is None:
        lead['note'] = d['rating']
        changes.append('rating')
    if d['reviews'] is not None and lead.get('nombre_avis') is None:
        lead['nombre_avis'] = d['reviews']
        changes.append('reviews')
    lead['placesCheckedAt'] = now_iso()
    return changes
