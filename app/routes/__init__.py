""" Root of routes package. """

from functools import wraps

from http import HTTPStatus

from flask import abort
from flask_login import current_user

# -------------------------------------------------------------------------------------------------

def api_login_required(func):

    # TODO can we use this or similar in profile routes for the admin stuff?
    # TODO can we use this or similar in leaderboards routes for admin stuff?

    @wraps(func)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            return abort(HTTPStatus.UNAUTHORIZED)

        return func(*args, **kwargs)

    return decorated_function

# -------------------------------------------------------------------------------------------------

from .auth import logout
from .auth.wca import wca_login, wca_authorize, wca_assoc
from .auth.reddit import reddit_login, reddit_authorize, reddit_assoc, admin_login
from .home import index, prompt_login
from .admin import confirm_gift_code_recipient, deny_gift_code_recipient, add_gift_codes
from .util import prev_results
from .results import results_list
from .user import profile
from .user.settings.reddit_settings_routes import reddit_settings
from .user.settings.wca_settings_routes import wca_settings
from .user.settings.timer_settings_routes import timer_settings
from .user.settings.event_settings_routes import events_settings
from .events import event_results, sum_of_ranks, event_results_export
from .timer import timer_page
from .export import export
