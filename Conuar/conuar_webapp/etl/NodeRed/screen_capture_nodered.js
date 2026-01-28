/**
 * NodeRed Function: Screen Recording Control (Updated)
 *
 * Outputs:
 * - Output 1: Original PLC data message (always sent)
 * - Output 2: OBS recording command (only when state changes)
 *
 * OBS command format: { payload: { requestType: "StartRecord" | "StopRecord" } }
 */

function decodeString(buf, name) {
    if (!buf || !Array.isArray(buf) || buf.length < 2) return null;
    let realLen = buf[1];
    let chars = buf.slice(2, 2 + realLen);
    return String.fromCharCode.apply(null, chars);
}

function isBooleanTrue(value) {
    if (typeof value === 'boolean') return value;
    if (typeof value === 'string') return value.toLowerCase().trim() === 'true' || value.trim() === '1';
    if (typeof value === 'number') return value === 1;
    return false;
}

// Decode buffer fields
let ID_Control = decodeString(msg.payload.ID_Control, 'ID_Control');
let Nombre_Control = decodeString(msg.payload.Nombre_Control, 'Nombre_Control');
let ID_EC = decodeString(msg.payload.ID_EC, 'ID_EC');
let NombreCiclo = decodeString(msg.payload.NombreCiclo, 'NombreCiclo');
msg.payload.ID_Control = ID_Control;
msg.payload.Nombre_Control = Nombre_Control;
msg.payload.ID_EC = ID_EC;
msg.payload.NombreCiclo = NombreCiclo;
msg.payload.datetime = (new Date()).toISOString();

// Decode/handle CicloActivo
let CicloActivo = msg.payload.CicloActivo;
if (CicloActivo && Array.isArray(CicloActivo)) {
    CicloActivo = decodeString(CicloActivo, 'CicloActivo');
}
let cicloActivoCurrent = isBooleanTrue(CicloActivo);

let cicloActivoPrevious = flow.get('cicloActivoPrevious') || false;

let recordingCommand = null;

if (cicloActivoCurrent && !cicloActivoPrevious) {
    // Start recording
    recordingCommand = {
        requestType: "StartRecord"
    };
    node.warn(">>> Inspection cycle STARTED - Starting screen recording");
    flow.set('currentNombreCiclo', NombreCiclo || 'UNKNOWN');
    flow.set('currentID_EC', ID_EC || 'UNKNOWN');
} else if (!cicloActivoCurrent && cicloActivoPrevious) {
    // Stop recording
    recordingCommand = {
        requestType: "StopRecord"
    };
    node.warn(">>> Inspection cycle ENDED - Stopping screen recording");
}

flow.set('cicloActivoPrevious', cicloActivoCurrent);

// If there's a recording command, set up OBS command payload
if (recordingCommand) {
    // OBS webhook connector expects: requestType (string) and requestData (object)
    // Ensure requestType is explicitly a string, not an object reference
    let requestTypeStr = String(recordingCommand.requestType);
    
    msg.payload = {
        requestType: requestTypeStr,  // string: "StartRecord" or "StopRecord"
        requestData: {}  // object (required by OBS connector, can be empty)
    };
    
    // Return message with OBS command structure
    return msg;
}

// If no recording command, return null to avoid sending invalid data to OBS connector
return null;