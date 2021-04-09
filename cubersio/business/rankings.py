""" Business logic for determining user site rankings and PBs. """

from collections import OrderedDict
from datetime import datetime
import json
from timeit import default_timer

from ranking import Ranking

from cubersio import DB
from cubersio.util.events.mbld import MbldSolve
from cubersio.persistence.models import Competition, CompetitionEvent, Event, UserEventResults, User,\
    UserSiteRankings, EventFormat
from cubersio.persistence.events_manager import get_all_events, get_all_WCA_events
from cubersio.persistence.user_site_rankings_manager import bulk_update_site_rankings
from cubersio.util.sorting import sort_personal_best_records


def calculate_user_site_rankings():
    """ Calculate user event site rankings based on PBs. """

    all_events = [e for e in get_all_events() if e.name != "COLL"]
    wca_event_ids = set(e.id for e in get_all_WCA_events())

    # These are of the form dict[Event, [ordered list of PersonalBestRecords]]
    events_pb_singles = dict()
    events_pb_averages = dict()

    # These are of the form dict[Event, dict[user ID, index in ordered PB records list]]
    events_pb_singles_ix = dict()
    events_pb_averages_ix = dict()

    # These are of the form dict[Event, int]
    events_singles_len = dict()
    events_averages_len = dict()

    # All user IDs seen, so we only iterate over users that have participated in something
    all_user_ids = set()

    t0 = default_timer()

    for event in all_events:

        e0 = default_timer()

        # Retrieve the the ordered list of PersonalBestRecords for singles for this event
        ordered_pb_singles = get_ordered_pb_singles_for_event(event.id)

        # If nobody at all has competed in this event, just move on to the next
        if not ordered_pb_singles:
            continue

        events_pb_singles[event] = ordered_pb_singles
        events_singles_len[event] = len(ordered_pb_singles)

        # Iterate the ordered PB singles, recording which users we've seen, and also building a map of the user ID to
        # their index in the ordered PB singles list, so we don't have to iterate that list for every user to find them
        user_single_ix_map = dict()
        for i, pb_record in enumerate(ordered_pb_singles):
            user_single_ix_map[pb_record.user_id] = i
            all_user_ids.add(pb_record.user_id)

        events_pb_singles_ix[event] = user_single_ix_map

        # Retrieve the the ordered list of PersonalBestRecords for averages for this event
        ordered_pb_averages = get_ordered_pb_averages_for_event(event.id)
        events_pb_averages[event] = ordered_pb_averages
        events_averages_len[event] = len(ordered_pb_averages)

        # Iterate the ordered PB averages, recording which users we've seen, and also building a map of the user ID to
        # their index in the ordered PB averages list, so we don't have to iterate that list for every user to find them
        user_average_ix_map = dict()
        for i, pb_record in enumerate(ordered_pb_averages):
            user_average_ix_map[pb_record.user_id] = i
            all_user_ids.add(pb_record.user_id)

        events_pb_averages_ix[event] = user_average_ix_map

        e1 = default_timer()
        print(f"[RANKINGS] {e1-e0}s elapsed to retrieve ordered PB data for {event.name}.")

    # Iterate through all users to determine their site rankings and PBs
    bulk_update_count = 0
    bulk_site_rankings = list()
    for user_id in all_user_ids:
        u0 = default_timer()
        # Calculate site rankings for the user
        rankings = _calculate_site_rankings_for_user(user_id, events_pb_singles, events_pb_singles_ix,
                                                     events_singles_len, events_pb_averages, events_pb_averages_ix,
                                                     events_averages_len, wca_event_ids, all_events)

        bulk_site_rankings.append(rankings)
        bulk_update_count += 1
        u1 = default_timer()
        print(f"[RANKINGS] {u1 - u0}s elapsed to calculate site rankings for user ID {user_id}.")

        if bulk_update_count == 250:
            db0 = default_timer()
            # Save to the database
            bulk_update_site_rankings(bulk_site_rankings)
            db1 = default_timer()
            print(f"[RANKINGS] {db1 - db0}s elapsed to update rankings for {bulk_update_count} users in database.")
            bulk_update_count = 0
            bulk_site_rankings = list()

    if bulk_site_rankings:
        bulk_update_site_rankings(bulk_site_rankings)

    t1 = default_timer()
    print(f"[RANKINGS] {t1 - t0}s elapsed to fully complete site rankings.")


def _calculate_site_rankings_for_user(user_id, event_singles_map, event_singles_ix_map, events_singles_len,
                                      event_averages_map, event_averages_ix_map, events_averages_len, wca_event_ids,
                                      all_events):
    """ TODO update this description for correct return type.
    Returns a dict of the user's PB singles and averages for all events they've participated in,
    as well as their rankings amongst the site's users. Format is:
    dict[event ID][(single, single_site_ranking, average, average_site_ranking)] """

    # Holds the user's various types of rankings for each event
    user_rankings_data = OrderedDict()

    # Create the actual UserSiteRankings object to stick the data in when we're done, which will hold both the raw
    # ranking data as well as sum of ranks, total Kinchranks, etc
    user_site_rankings = UserSiteRankings()
    user_site_rankings.user_id = user_id

    # Start off all sum of ranks stats at 0
    # [single, average]
    sor_all     = [0, 0]
    sor_wca     = [0, 0]
    sor_non_wca = [0, 0]

    # Hold site-wide Kinchrank (for WCA-only, non-WCA-only, and all events) for this user
    overall_kinchranks = list()
    wca_kinchranks     = list()
    non_wca_kinchranks = list()

    for event in all_events:
        pb_single    = ''
        single_rank  = ''
        pb_average   = ''
        average_rank = ''
        event_kinch  = 0

        event_is_wca = event.id in wca_event_ids

        # Get the lists ranked singles and averages for the current event. If there's nothing in the map for that event,
        # nobody has competed in it yet, so we can skip to the next.
        ranked_singles = event_singles_map.get(event, None)
        if not ranked_singles:
            continue
        ranked_averages = event_averages_map[event]
        singles_ix_map = event_singles_ix_map[event]
        averages_ix_map = event_averages_ix_map[event]

        # See if there's a result for our user in the singles
        single_ix = singles_ix_map.get(user_id, None)
        if single_ix:
            pb_single   = ranked_singles[single_ix].personal_best
            single_rank = ranked_singles[single_ix].numerical_rank

        # If our user has no single for this event, their site ranking is (1 + number of people in this event)
        if not pb_single:
            single_rank = events_singles_len[event] + 1

        # See if there's a result for our user in the averages. It's ok if there isn't, either because the user doesn't
        # have an average or this event doesn't have averages. We'll just record blank values.
        average_ix = averages_ix_map.get(user_id, None)
        if average_ix:
            pb_average   = ranked_averages[average_ix].personal_best
            average_rank = ranked_averages[average_ix].numerical_rank

        # If our user has no average for this event, their site ranking is (1 + number of people in this event)
        if not pb_average:
            average_rank = events_averages_len[event] + 1

        # Determine Kinchrank component for this event
        # TODO: add explanations below
        if event.name == 'MBLD':
            best_mbld = int(ranked_singles[0].personal_best)
            baseline_mbld = MbldSolve(best_mbld).sort_value
            if pb_single and pb_single != 'DNF':
                coded_mbld = int(pb_single)
                this_mbld  = MbldSolve(coded_mbld).sort_value
                event_kinch = round((this_mbld / baseline_mbld) * 100, 3)
        elif event.name in ('FMC', '3BLD'):
            single_kinch = 0
            average_kinch = 0
            if pb_single and pb_single != 'DNF':
                single_kinch = round(int(ranked_singles[0].personal_best) / int(pb_single) * 100, 3)
            if pb_average and pb_average != 'DNF':
                average_kinch = round(int(ranked_averages[0].personal_best) / int(pb_average) * 100, 3)
            event_kinch = max([single_kinch, average_kinch])
        elif event.eventFormat in (EventFormat.Bo1, EventFormat.Bo3):
            if pb_single and pb_single != 'DNF':
                event_kinch = round(int(ranked_singles[0].personal_best) / int(pb_single) * 100, 3)
        else:
            if pb_average and pb_average != 'DNF':
                event_kinch = round(int(ranked_averages[0].personal_best) / int(pb_average) * 100, 3)

        # Accumulate Kinchranks
        overall_kinchranks.append(event_kinch)
        if event_is_wca:
            wca_kinchranks.append(event_kinch)
        else:
            non_wca_kinchranks.append(event_kinch)

        # Records the user's rankings, PBs, and Kinchrank component for this event
        user_rankings_data[event.id] = (pb_single, single_rank, pb_average, average_rank, format(event_kinch, '.3f'))

        # Accumulate sum of ranks
        sor_all[0] += single_rank
        sor_all[1] += average_rank if average_rank else 0
        if event_is_wca:
            sor_wca[0] += single_rank
            sor_wca[1] += average_rank if average_rank else 0
        else:
            sor_non_wca[0] += single_rank
            sor_non_wca[1] += average_rank if average_rank else 0

    # Save the event site rankings data as serialized json into the UserSiteRankings
    # Set values for Sum Of Ranks, single and average, for combined, WCA, and non-WCA
    # Set values for Kinchranks, for combined, WCA, and non-WCA
    user_site_rankings.data                = json.dumps(user_rankings_data)
    user_site_rankings.timestamp           = datetime.now()
    user_site_rankings.sum_all_single      = sor_all[0]
    user_site_rankings.sum_all_average     = sor_all[1]
    user_site_rankings.sum_wca_single      = sor_wca[0]
    user_site_rankings.sum_wca_average     = sor_wca[1]
    user_site_rankings.sum_non_wca_single  = sor_non_wca[0]
    user_site_rankings.sum_non_wca_average = sor_non_wca[1]

    if overall_kinchranks:
        user_site_rankings.all_kinchrank = round(sum(overall_kinchranks) / (len(overall_kinchranks) + 0.0), 3)
    else:
        user_site_rankings.all_kinchrank = 0

    if wca_kinchranks:
        user_site_rankings.wca_kinchrank = round(sum(wca_kinchranks) / (len(wca_kinchranks) + 0.0), 3)
    else:
        user_site_rankings.wca_kinchrank = 0

    if non_wca_kinchranks:
        user_site_rankings.non_wca_kinchrank = round(sum(non_wca_kinchranks) / (len(non_wca_kinchranks) + 0.0), 3)
    else:
        user_site_rankings.non_wca_kinchrank = 0

    return user_site_rankings

# -------------------------------------------------------------------------------------------------
#                        Stuff for retrieving ordered lists of PB records
# -------------------------------------------------------------------------------------------------


# We don't want to use a dictionary here, that defeats the purpose of developer-readable objects.
# Can't use a namedtuple, because the values set there are immutable, and we need to be able to modify the rank,
# which isn't known until after these records are created.
class PersonalBestRecord:
    """ Property bag class for encapsulating a user's PB record. """

    def __init__(self, **kwargs):
        self.user_id          = kwargs.get('user_id')
        self.comp_id          = kwargs.get('comp_id')
        self.username         = kwargs.get('username')
        self.comp_title       = kwargs.get('comp_title')
        self.personal_best    = kwargs.get('personal_best')
        self.comment          = kwargs.get('comment')
        self.user_is_verified = kwargs.get('user_is_verified')
        self.rank             = '-1'
        self.numerical_rank   = '-1'


def _build_personal_best_record(query_tuple):
    """ Builds a PersonalBestRecord from the 5-tuple returned from the ordered PB queries below.
    The tuple looks like (user_id, single/average, comp_id, comp_title, username). """

    user_id, result, comp_id, comp_title, username, comment, user_is_verified = query_tuple
    return PersonalBestRecord(personal_best=result, user_id=user_id, username=username, comp_id=comp_id,
                              comp_title=comp_title, comment=comment, user_is_verified=user_is_verified)


def _determine_ranks(personal_bests):
    """ Takes an ordered list of PersonalBestRecords and assigns each PersonalBestRecord a rank.
    Ranks are the same for PersonalBestRecords with identical times.
    Ex: [12, 13, 14, 14, 15] would have ranks [1, 2, 3, 3, 5] """

    # If `personal_bests` is empty, we can't use the ranking mechanism below, so just return
    # the empty list
    if not personal_bests:
        return personal_bests

    # Build a list of just the time values of the personal bests, to be fed into the ranking
    # mechanism. If the PB time value cannot be interpreted as an int, it's probably a DNF so
    # just pretend it's some humongous value which would sorted to the end
    times_values = list()
    for personal_best in personal_bests:
        try:
            times_values.append(int(personal_best.personal_best))
        except ValueError:
            times_values.append(9999999999999)

    # Rank the list of times. The result from this is (rank, time value) where the index
    # of the element for each time value doesn't change from the input to the output
    ranked_times = list(Ranking(times_values, start=1, reverse=True))

    # Give each PersonalBestRecord its rank from the corresponding element in ranked_times
    ranks_seen = set()
    for i, personal_best in enumerate(personal_bests):
        rank = ranked_times[i][0]
        if rank not in ranks_seen:
            ranks_seen.add(rank)
            personal_best.rank = rank
            personal_best.numerical_rank = rank
        else:
            personal_best.rank = ''
            personal_best.numerical_rank = rank

    return personal_bests


def get_ordered_pb_singles_for_event(event_id):
    """ Gets a list of PersonalBestRecords, comprised of the fastest single which doesn't belong to
    a blacklisted result, one per user, for the specified event, sorted by single value. """

    results = DB.session.\
        query(UserEventResults).\
        join(User).\
        join(CompetitionEvent).\
        join(Event).\
        join(Competition).\
        filter(Event.id == event_id).\
        filter(UserEventResults.is_complete).\
        filter(UserEventResults.is_latest_pb_single).\
        filter(UserEventResults.is_blacklisted.isnot(True)).\
        group_by(UserEventResults.id, UserEventResults.user_id, UserEventResults.single, Competition.id,
                 Competition.title, User.username, User.is_verified).\
        values(UserEventResults.user_id, UserEventResults.single, Competition.id, Competition.title, User.username,
               UserEventResults.comment, User.is_verified)

    # NOTE: if adding anything to this tuple being selected in values(...) above, add it to the
    # end so that code indexing this tuple doesn't get all jacked. Make sure to make an identical
    # addition to `get_ordered_pb_averages_for_event` and update `_build_PersonalBestRecord`

    personal_bests = [_build_personal_best_record(result) for result in results]
    personal_bests.sort(key=sort_personal_best_records)
    personal_bests = _determine_ranks(personal_bests)

    return personal_bests


def get_ordered_pb_averages_for_event(event_id):
    """ Gets a list of PersonalBestRecords, comprised of the fastest average which doesn't belong to
    a blacklisted result, one per user, for the specified event, sorted by average value.  """

    results = DB.session.\
        query(UserEventResults).\
        join(User).\
        join(CompetitionEvent).\
        join(Event).\
        join(Competition).\
        filter(Event.id == event_id).\
        filter(UserEventResults.is_complete).\
        filter(UserEventResults.is_latest_pb_average).\
        filter(UserEventResults.is_blacklisted.isnot(True)).\
        group_by(UserEventResults.id, UserEventResults.user_id, UserEventResults.average, Competition.id,
                 Competition.title, User.username, User.is_verified).\
        values(UserEventResults.user_id, UserEventResults.average, Competition.id, Competition.title, User.username,
               UserEventResults.comment, User.is_verified)

    # NOTE: if adding anything to this tuple being selected in values(...) above, add it to the
    # end so that code indexing this tuple doesn't get all jacked. Make sure to make an identical
    # addition to `get_ordered_pb_singles_for_event` and update `_build_PersonalBestRecord`

    personal_bests = [_build_personal_best_record(result) for result in results]

    # Some events don't have averages, so it's ok to just return an empty list. Checking here
    # instead of checking `results` above, because `results` is a generator and the contents have't
    # been iterated yet
    if not personal_bests:
        return list()

    personal_bests.sort(key=sort_personal_best_records)
    personal_bests = _determine_ranks(personal_bests)

    return personal_bests
