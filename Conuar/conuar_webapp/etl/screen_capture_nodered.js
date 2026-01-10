/**
 * NodeRed Function: Screen Recording Control
 * 
 * This function monitors CicloActivo state changes and generates recording commands.
 * When CicloActivo changes from FALSE/0 to TRUE/1, it outputs a 'start' recording command.
 * When CicloActivo changes from TRUE/1 to FALSE/0, it outputs a 'stop' recording command.
 * 
 * Outputs:
 * - Output 1: Original PLC data message (always sent)
 * - Output 2: Recording command message (only when state changes)
 * 
 * Recording command format:
 * {
 *   action: 'start' | 'stop',
 *   nombreCiclo: string,
 *   id_ec: string,
 *   id_control: string (only for start),
 *   timestamp: ISO string
 * }
 * 
 * Configure the function node with 2 outputs to separate PLC data from recording commands.
 * Connect output 2 to an exec node or other node that handles screen recording.
 */

function decodeString(buf, name) {
    if (!buf || !Array.isArray(buf) || buf.length < 2) {
        //node.warn("Buffer for " + name + " is undefined, not an array, or too short: " + JSON.stringify(buf));
        return null;
    }
    let maxLen = buf[0];
    let realLen = buf[1];
    let chars = buf.slice(2, 2 + realLen);
    let result = String.fromCharCode.apply(null, chars);
    //node.warn("Decoded " + name + ": '" + result + "' from buffer: " + JSON.stringify(buf));
    return result;
}

function isBooleanTrue(value) {
    if (typeof value === 'boolean') {
        return value;
    }
    if (typeof value === 'string') {
        return value.toLowerCase().trim() === 'true' || value.trim() === '1';
    }
    if (typeof value === 'number') {
        return value === 1;
    }
    return false;
}

// Decode string fields from buffers
let ID_Control = decodeString(msg.payload.ID_Control, 'ID_Control');
msg.payload.ID_Control = ID_Control;

let Nombre_Control = decodeString(msg.payload.Nombre_Control, 'Nombre_Control');
msg.payload.Nombre_Control = Nombre_Control;

let ID_EC = decodeString(msg.payload.ID_EC, 'ID_EC');
msg.payload.ID_EC = ID_EC;

let NombreCiclo = decodeString(msg.payload.NombreCiclo, 'NombreCiclo');
msg.payload.NombreCiclo = NombreCiclo;

msg.payload.datetime = (new Date()).toISOString();

// Get CicloActivo value (handle both buffer and direct value)
let CicloActivo = msg.payload.CicloActivo;
if (CicloActivo && Array.isArray(CicloActivo)) {
    // If it's a buffer, decode it
    CicloActivo = decodeString(CicloActivo, 'CicloActivo');
}
let cicloActivoCurrent = isBooleanTrue(CicloActivo);

// Get previous state from flow context (flow-scoped storage)
// Use flow.get() and flow.set() for persistent storage across messages
let cicloActivoPrevious = flow.get('cicloActivoPrevious') || false;

// Detect state changes
let recordingCommand = null;

// State change: FALSE -> TRUE (start recording)
if (cicloActivoCurrent && !cicloActivoPrevious) {
    recordingCommand = {
        action: 'start',
        nombreCiclo: NombreCiclo || 'UNKNOWN',
        id_ec: ID_EC || 'UNKNOWN',
        id_control: ID_Control || '',
        timestamp: msg.payload.datetime,
        requestType: "StartRecord"
    };
    node.warn(">>> Inspection cycle STARTED - Starting screen recording");
    node.warn("    NombreCiclo: " + recordingCommand.nombreCiclo + ", ID_EC: " + recordingCommand.id_ec);
}

// State change: TRUE -> FALSE (stop recording)
else if (!cicloActivoCurrent && cicloActivoPrevious) {
    recordingCommand = {
        action: 'stop',
        nombreCiclo: flow.get('currentNombreCiclo') || 'UNKNOWN',
        id_ec: flow.get('currentID_EC') || 'UNKNOWN',
        timestamp: msg.payload.datetime,
        requestType: "StopRecord"
    };
    node.warn(">>> Inspection cycle ENDED - Stopping screen recording");
    node.warn("    NombreCiclo: " + recordingCommand.nombreCiclo + ", ID_EC: " + recordingCommand.id_ec);
}

// Update flow context with current state
flow.set('cicloActivoPrevious', cicloActivoCurrent);
if (cicloActivoCurrent) {
    // Store current inspection info while recording
    flow.set('currentNombreCiclo', NombreCiclo || 'UNKNOWN');
    flow.set('currentID_EC', ID_EC || 'UNKNOWN');
}

// If there's a recording command, create a separate message for it
if (recordingCommand) {
    // Create a new message for the recording command
    let recordingMsg = {
        requestType: recordingCommand.requestType
        //payload: recordingCommand,
        //topic: 'screen_recording',
        //timestamp: msg.payload.datetime
    };

    // Send both messages: the original PLC data and the recording command
    // The recording command will be sent to a different output
    return [msg, recordingMsg];
}

// No state change, just return the original message
return msg;