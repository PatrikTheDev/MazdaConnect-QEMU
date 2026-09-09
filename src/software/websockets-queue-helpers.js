// Lab correction: every queued item is [serialized message, sequence].
// Keep the original last-match lookup and delete all matching entries.
Websockets.prototype._isStack = function(type, sequence)
{
    var found = false;
    for (var i = 0; i < this._waitMsgArray.length; i++)
    {
        var entry = this._waitMsgArray[i];
        if (entry[1] == sequence && JSON.parse(entry[0]).msgType == type)
        {
            mStackOutput = entry[0];
            found = true;
        }
    }
    return found;
};

Websockets.prototype._delStack = function(type, sequence)
{
    for (var i = this._waitMsgArray.length - 1; i >= 0; i--)
    {
        var entry = this._waitMsgArray[i];
        if (entry[1] == sequence && JSON.parse(entry[0]).msgType == type)
            this._waitMsgArray.splice(i, 1);
    }
};
