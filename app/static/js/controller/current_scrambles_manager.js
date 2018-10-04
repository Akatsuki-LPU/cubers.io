(function() {
    var app = window.app;

    // The events the CurrentScramblesManager can emit
    var EVENT_NOTHING_TO_ATTACH     = "event_nothing_attached";
    var EVENT_NEW_SCRAMBLE_ATTACHED = "event_new_scramble_attached";

    /**
     * Manages the scrambles for the for the currently-active event
     */
    function CurrentScramblesManager() {
        app.EventEmitter.call(this);
        this._registerTimerEventHandlers();
    };
    CurrentScramblesManager.prototype = Object.create(app.EventEmitter.prototype);

    /**
     * Event handler for when events data gets updated. Advance the timer scramble to the next incomplete one
     * for the current competition event.
     */
    CurrentScramblesManager.prototype._advanceScrambleAfterTimerStop = function(timer_stop_data) {
        this._attachNextUnsolvedScramble(timer_stop_data.comp_event_id);

    };

    /**
     * Attach the scramble for the first incomplete solve for this competition event.
     */
    CurrentScramblesManager.prototype.attachFirstScramble = function(comp_event_id) {
        this._attachNextUnsolvedScramble(comp_event_id);
    };

    /**
     * Call eventsDataManager to get the next incomplete scramble. If there is one, attach it
     * to the timer and then emit an event so that solve card gets visually updated
     */
    CurrentScramblesManager.prototype._attachNextUnsolvedScramble = function(comp_event_id) {
        var nextIncompleteScramble = app.eventsDataManager.getNextIncompleteScramble(comp_event_id);
        if (nextIncompleteScramble) {
            app.timer.attachToScramble(nextIncompleteScramble.id);
            this.emit(EVENT_NEW_SCRAMBLE_ATTACHED, nextIncompleteScramble);
        } else {
            var event_name = app.eventsDataManager.getEventName(comp_event_id);
            this.emit(EVENT_NOTHING_TO_ATTACH, event_name);
        }
    };

    /**
     * Attach the timer and update solve card for the specified scramble ID and competition event ID
     */
    CurrentScramblesManager.prototype.attachSpecifiedScramble = function(comp_event_id, scramble_id) {
        var scramble = app.eventsDataManager.getSolveRecord(comp_event_id, scramble_id);
        if (scramble) {
            app.timer.attachToScramble(scramble.id);
            this.emit(EVENT_NEW_SCRAMBLE_ATTACHED, scramble);
        }
    };

    /**
     * Register handlers for events data manager events.
     */
    CurrentScramblesManager.prototype._registerTimerEventHandlers = function() {
        app.eventsDataManager.on(app.EVENT_SOLVE_RECORD_UPDATED, this._advanceScrambleAfterTimerStop.bind(this));
    };

    // Make CurrentScramblesManager and event names visible at app scope
    app.CurrentScramblesManager     = CurrentScramblesManager;
    app.EVENT_NOTHING_TO_ATTACH     = EVENT_NOTHING_TO_ATTACH;
    app.EVENT_NEW_SCRAMBLE_ATTACHED = EVENT_NEW_SCRAMBLE_ATTACHED;
})();