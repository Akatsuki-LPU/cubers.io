""" Routes related to saving results to the database. """

import json

from flask import request, abort
from flask_login import current_user

from app import CUBERS_APP
from app.persistence import comp_manager
from app.persistence.models import EventFormat
from app.persistence.user_manager import get_user_by_username
from app.persistence.user_results_manager import build_user_event_results, save_event_results_for_user,\
    build_all_user_results, are_results_different_than_existing, get_comment_id_by_comp_id_and_user
from app.persistence.comp_manager import get_competition, get_all_complete_user_results_for_comp_and_user
from app.util.reddit_util import build_times_string, convert_centiseconds_to_friendly_time,\
    build_comment_source_from_events_results, submit_comment_for_user, get_permalink_for_comp_thread,\
    update_comment_for_user, get_permalink_for_user_and_comment

# -------------------------------------------------------------------------------------------------

@CUBERS_APP.route('/save_event', methods=['POST'])
def save_event():
    """ A route for saving a specific event to the database. """

    if not current_user.is_authenticated:
        return abort(400, "authenticated users only")

    try:
        user_events_dict  = request.get_json()
        event_result = build_all_user_results(user_events_dict)[0]
        user = get_user_by_username(current_user.username)

        should_do_reddit_submit = event_result.is_complete and are_results_different_than_existing(event_result, user)

        saved_results = save_event_results_for_user(event_result, user)

        if should_do_reddit_submit:
            do_reddit_submit(saved_results.CompetitionEvent.Competition.id, user)

        return ('', 204) # intentionally empty, 204 No Content

    except Exception as ex:
        return abort(500, str(ex))


@CUBERS_APP.route('/event_summaries', methods=['POST'])
def get_event_summaries():
    """ A route for building an event summary which details the average or best (depending on
    the event format), and the constituent times with penalties, and best/worst indicated when
    appropriate.

    Ex: 15.24 = 14.09, 16.69, 14.94, (10.82), (18.39) --> for a Ao5 event
        6:26.83 = 6:46.17, 5:50.88, 6:43.44           --> for a Mo3 event """

    data = request.get_json()
    summaries = {event['comp_event_id']: build_summary(event) for event in data}

    return json.dumps(summaries)


@CUBERS_APP.route('/comment_url/<int:comp_id>')
def comment_url(comp_id):
    """ A route for retrieving the user's Reddit comment direct URL for a given competition event. """

    if not current_user.is_authenticated:
        return ""

    user = get_user_by_username(current_user.username)
    comment_id = get_comment_id_by_comp_id_and_user(comp_id, user)
    if not comment_id:
        return ""

    return get_permalink_for_user_and_comment(user, comment_id)


def build_summary(event):
    """ Builds the summary for the event and returns it. """

    build_results = build_user_event_results
    friendly = convert_centiseconds_to_friendly_time

    results = build_results(event['comp_event_id'], event['scrambles'], event['comment'])
    event_format = comp_manager.get_event_by_name(event['name']).eventFormat
    is_fmc   = event['name'] == 'FMC'
    is_blind = event['name'] in ('3BLD', '2BLD', '4BLD', '5BLD', 'MBLD')

    if event_format == EventFormat.Bo1:
        return friendly(results.single)

    best = results.single if (event_format == EventFormat.Bo3) else results.average
    if not is_fmc:
        best = friendly(best)
    else:
        best = (best/100)
        if best == int(best):
            best = int(best)

    times_string = build_times_string(results.solves, event_format, is_fmc, is_blind)
    return "{} = {}".format(best, times_string)


def do_reddit_submit(comp_id, user):
    """ Handle submitting a new, or updating an existing, Reddit comment. """

    comp = get_competition(comp_id)
    reddit_thread_id = comp.reddit_thread_id
    results = comp_manager.get_all_complete_user_results_for_comp_and_user(comp.id, user.id)
    comment_source = build_comment_source_from_events_results(results)

    previous_comment_id = get_comment_id_by_comp_id_and_user(comp.id, user)

    # this is a resubmission
    if previous_comment_id:
        _, comment_id = update_comment_for_user(user, previous_comment_id, comment_source)

    # new submission
    else:
        _, comment_id = submit_comment_for_user(user, reddit_thread_id, comment_source)

    if not comment_id:
        return

    for result in results:
        result.reddit_comment = comment_id
        save_event_results_for_user(result, user)