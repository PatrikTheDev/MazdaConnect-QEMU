
// Observe start/end independently of the manager's cleanup listeners. Do not
// read styles, cancel events, or modify the target's animation state here.
['animationstart', 'animationend'].forEach(function(type) {
    document.addEventListener(type, function(evt) {
        if (String(evt.animationName).indexOf('transitions_keyframes_') !== 0) return;
        log.info('LAB_TRANSITION document event ' + evt.type + ' target=' + evt.target.id +
                 ' name=' + evt.animationName + ' elapsed=' + evt.elapsedTime);
    }, true);
});

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
