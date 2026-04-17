from django.utils import translation

class ForceMarathiMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if not request.session.get('django_language'):
            translation.activate('mr')
            request.session['django_language'] = 'mr'
        else:
            translation.activate(request.session['django_language'])

        request.LANGUAGE_CODE = translation.get_language()
        return self.get_response(request)