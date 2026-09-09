
// Read computed styles only after the original watchdog has already fired.
Transitions.prototype._labTracePending = function() {
    for (var key in this._animationTargetDescriptions) {
        if (!this._animationTargetDescriptions.hasOwnProperty(key)) continue;
        var item = this._animationTargetDescriptions[key];
        log.info('LAB_TRANSITION pending ' + key + ' incomplete=' + item.isIncomplete);
        var target = item.target;
        if (!target) continue;
        log.info('LAB_TRANSITION target ' + target.id + ' classes=' + target.className);
        var style = getComputedStyle(target);
        ['animationName','animationDuration','animationDelay','animationPlayState','opacity','display','visibility'].forEach(function(name) {
            log.info('LAB_TRANSITION style ' + target.id + ' ' + name + '=' + style[name]);
        });
    }
};
