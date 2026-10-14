/* Lab-only shortcuts. ES5 for the original Opera. No fake backend responses. */
(function () {
    var send = framework.sendEventToMmui;
    framework.sendEventToMmui = function (uiaId, eventId, params, fromVui) {
        if (uiaId === "diag" || (uiaId === "syssettings" && eventId === "SelectDiagnostics")) {
            log.info("LAB_FACTORY_EVENT " + eventId + " " + JSON.stringify(params || {}));
        }
        return send.call(this, uiaId, eventId, params, fromVui);
    };
    document.addEventListener("keydown", function (event) {
        var key = event.keyCode;
        if (key < 113 || key > 115 || event.repeat) { return; }
        event.preventDefault();
        event.stopPropagation();
        if (!framework.websockets._mmuiWs || framework.websockets._mmuiWs.readyState !== 1) {
            log.warn("LAB_FACTORY_DEBUG MMUI websocket is not ready");
            return;
        }
        if (key === 113) {
            framework.sendEventToMmui("syssettings", "SelectDiagnostics");
            return;
        }
        var app = framework.getAppInstance("diag");
        if (framework.getCurrentApp() !== "diag" || framework.getCurrCtxtId() !== "Diagnostics" || !app) {
            log.warn("LAB_FACTORY_DEBUG open diagnostics with F2 first");
            return;
        }
        if (key === 114) {
            framework.sendEventToMmui("diag", app._cachedTestModeState === "JCITestMode" ? "DeactivateJCITest" : "ActivateJCITest");
        } else if (app._cachedTestModeState === "JCITestMode") {
            framework.sendEventToMmui("diag", "ReadDTC", {payload: {testId: 11}});
        } else {
            log.warn("LAB_FACTORY_DEBUG enable JCI Test Mode with F3 before F4");
        }
    }, true);
    log.info("LAB_FACTORY_DEBUG ready: F2 diagnostics, F3 JCI mode toggle, F4 script menu");
}());
