import json

from django.http import HttpResponse


class ModuleGateMiddleware:
    """Block a signed-in user from API sections their role does not include.

    Login, punch, notifications, and the personal desk stay open. WhatsApp's
    Meta webhook stays public. Views that already allow anonymous requests are
    left alone when there is no Bearer token.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        module = None
        user = None
        path = request.path or ''
        if path.startswith('/api/'):
            from .access import can, module_for_path
            module = module_for_path(path)
            if module:
                user = _bearer_user(request)
                if user is not None and user.is_authenticated and not can(user, module):
                    body = json.dumps({
                        'detail': 'Your role does not include this section.',
                        'module': module,
                    })
                    return HttpResponse(body, status=403, content_type='application/json')
        return self.get_response(request)


def _bearer_user(request):
    header = request.META.get('HTTP_AUTHORIZATION', '')
    if not header.startswith('Bearer '):
        return None
    try:
        from rest_framework_simplejwt.authentication import JWTAuthentication
        validated = JWTAuthentication().authenticate(request)
    except Exception:
        return None
    if not validated:
        return None
    return validated[0]
