import logging
import os

from social_core.backends.open_id_connect import OpenIdConnectAuth

from hub.models import lookup_course, update_UserCourseBindings
from kooplex.settings import KOOPLEX

logger = logging.getLogger(__name__)


class HydraOpenID(OpenIdConnectAuth):
    name = 'hydraoidc'
    OIDC_ENDPOINT = 'https://hydra-dev.elte.hu:4444'

    def get_redirect_uri(self, state = None):
        """Build redirect with redirect_state parameter."""
        base_url = KOOPLEX.get('base_url', 'http://localhost')
        url = os.path.join(base_url, "hub/oauth/complete/hydraoidc/")
        if self.REDIRECT_STATE and state:
            uri = url_add_parameters(url, {'redirect_state': state})
        else:
            uri = url
        return uri

    def get_user_details(self, response):
        return {
            'username': response['idp_user'],
            'email': response['mail'],
            'fullname': response['displayName'],
            'first_name': response['firstName'],
            'last_name': response['lastName'],
        }

    def authenticate(self, request, **credentials):
        def updater(key, is_teacher):
            for courseid in response.get(key, []):
                if '/' in courseid:
                    coursename, flag = courseid.split('/', 1)
                    if flag.count('/') > 0:
                        flag = flag.replace('/', '.')
                        logger.error("Too many '/' symbol in course id: %s (user %s) flag is now: %s" % (courseid, request.user, flag))
                else:
                    coursename = courseid
                    flag = None
                course = lookup_course(coursename)
                bindings.append({ 'course': course, 'flag': flag, 'is_teacher': is_teacher })
        user = super(HydraOpenID, self).authenticate(request, **credentials)
        response = credentials.get('response', {})
        logger.debug("IDP resp %s" % response)
        try:
            logger.debug("Authenticated (username) %s" % user.username)
        except:
            pass
        bindings = []
        # currently held courses
        updater('niifEduPersonHeldCourse', is_teacher = True)
        # currently attended courses
        updater('niifEduPersonAttendedCourse', is_teacher = False)
        update_UserCourseBindings(user, bindings)
        return user
