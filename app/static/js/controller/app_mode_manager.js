(function() {
    var app = window.app;

    // The events the AppModeManager can emit
    var EVENT_APP_MODE_TO_MAIN = 'event_app_mode_to_main';
    var EVENT_APP_MODE_TO_TIMER = 'event_app_mode_to_timer';
    var EVENT_APP_MODE_TO_SUMMARY = 'event_app_mode_to_summary';

    /**
     * Manages the overall state of the web app - which screen is currently visible,
     * and the transitions between them.
     */
    function AppModeManager() {
        app.EventEmitter.call(this);

        this._wire_event_card_click();
        this._wire_review_button();
    };
    AppModeManager.prototype = Object.create(app.EventEmitter.prototype);

    /**
     * When clicking on an event card, shows the timer panel for the selected event
     */
    AppModeManager.prototype._wire_event_card_click = function() {
        $('.event-card').click(function(e) {
            var $event = $(e.target).closest('.event-card');
            this.emit(EVENT_APP_MODE_TO_TIMER, $event);
        }.bind(this));
    };

    /**
     * When clicking the review solves button, go to the summary page
     */
    AppModeManager.prototype._wire_review_button = function() {
        $('#times-summary>.btn-summary').click(function() {
            this.emit(EVENT_APP_MODE_TO_SUMMARY);
        }.bind(this));
    };

    /**
     * When clicking the button to return to the events panel, show the main panel
     * and hide the others
     */
    AppModeManager.prototype.wire_return_to_events_from_timer = function() {
        $('#return-to-events>.btn-return').click(function(){
            this.emit(EVENT_APP_MODE_TO_MAIN);
        }.bind(this));
    },

    /**
     * When clicking the button to return to the events panel, show 
     */
    AppModeManager.prototype.wire_return_to_events_from_summary = function() {
        $('#summary-return-to-events>.btn-return').click(function(){
            this.emit(EVENT_APP_MODE_TO_MAIN);
        }.bind(this));
    };

    app.AppModeManager = AppModeManager;
    app.EVENT_APP_MODE_TO_MAIN = EVENT_APP_MODE_TO_MAIN;
    app.EVENT_APP_MODE_TO_TIMER = EVENT_APP_MODE_TO_TIMER;
    app.EVENT_APP_MODE_TO_SUMMARY = EVENT_APP_MODE_TO_SUMMARY;
})();