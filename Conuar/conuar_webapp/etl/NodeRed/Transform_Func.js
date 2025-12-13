var now = new Date();

function decodeString(buf) {
    let maxLen = buf[0];
    let realLen = buf[1];
    let chars = buf.slice(2, 2 + realLen);
    return String.fromCharCode.apply(null, chars);
}

let ID_Control = decodeString(msg.payload.ID_Control);
msg.payload.ID_Control = ID_Control

let Nombre_Control = decodeString(msg.payload.Nombre_Control);
msg.payload.Nombre_Control = Nombre_Control

let ID_EC = decodeString(msg.payload.ID_EC);
msg.payload.ID_EC = ID_EC

let NombreCiclo = decodeString(msg.payload.NombreCiclo);
msg.payload.NombreCiclo = NombreCiclo

let datetime = now.toISOString();
msg.payload.datetime = datetime

return msg;