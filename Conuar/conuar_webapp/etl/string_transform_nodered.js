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


let ID_Control = decodeString(msg.payload.ID_Control, 'ID_Control');
msg.payload.ID_Control = ID_Control;

let Nombre_Control = decodeString(msg.payload.Nombre_Control, 'Nombre_Control');
msg.payload.Nombre_Control = Nombre_Control;

let ID_EC = decodeString(msg.payload.ID_EC, 'ID_EC');
msg.payload.ID_EC = ID_EC;

let NombreCiclo = decodeString(msg.payload.NombreCiclo, 'NombreCiclo');
msg.payload.NombreCiclo = NombreCiclo;

msg.payload.datetime = (new Date()).toISOString();

return msg;