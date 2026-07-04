// ===============================
// GLOBALS
// ===============================

let currentPrivateKey = null;
let currentPublicKey = null;
let currentDeviceId = null;


// ===============================
// RANDOM DEVICE ID
// ===============================

function generateDeviceId() {
    return crypto.randomUUID();
}


// ===============================
// BASE64 HELPERS
// ===============================

function bytesToBase64(bytes) {

    let binary = "";

    for (const b of bytes) {
        binary += String.fromCharCode(b);
    }

    return btoa(binary);
}


function base64ToBytes(base64) {

    return Uint8Array.from(
        atob(base64),
        c => c.charCodeAt(0)
    );

}


// Base64URL

function bytesToBase64Url(bytes) {

    return bytesToBase64(bytes)
        .replace(/\+/g, "-")
        .replace(/\//g, "_")
        .replace(/=+$/, "");

}


function base64UrlToBytes(base64url) {

    const base64 = base64url
        .replace(/-/g, "+")
        .replace(/_/g, "/");

    const padded =
        base64 +
        "=".repeat((4 - base64.length % 4) % 4);

    return base64ToBytes(padded);

}



// ===============================
// AES KEY (PEK)
// ===============================

async function generatePEK() {

    return crypto.subtle.generateKey(
        {
            name: "AES-GCM",
            length: 256
        },
        true,
        ["encrypt", "decrypt"]
    );

}


async function exportAESKey(key) {

    const raw =
        await crypto.subtle.exportKey(
            "raw",
            key
        );

    return bytesToBase64(
        new Uint8Array(raw)
    );

}


async function importAESKey(base64) {

    return crypto.subtle.importKey(
        "raw",
        base64ToBytes(base64),
        "AES-GCM",
        true,
        ["encrypt", "decrypt"]
    );

}



// ===============================
// AES ENCRYPT
// ===============================

async function encryptWithAES(text, key) {

    const iv =
        crypto.getRandomValues(
            new Uint8Array(12)
        );

    const encrypted =
        await crypto.subtle.encrypt(
            {
                name: "AES-GCM",
                iv
            },
            key,
            new TextEncoder().encode(text)
        );

    return {

        iv: bytesToBase64(iv),

        data: bytesToBase64(
            new Uint8Array(encrypted)
        )

    };

}


async function decryptWithAES(obj, key) {

    const decrypted =
        await crypto.subtle.decrypt(
            {

                name: "AES-GCM",

                iv: base64ToBytes(obj.iv)

            },

            key,

            base64ToBytes(obj.data)

        );

    return new TextDecoder().decode(
        decrypted
    );

}



// ===============================
// RSA KEYPAIR
// ===============================

async function generateRSAKeyPair() {

    return crypto.subtle.generateKey(
        {

            name: "RSA-OAEP",

            modulusLength: 4096,

            publicExponent:
                new Uint8Array([1,0,1]),

            hash: "SHA-256"

        },

        true,

        ["encrypt","decrypt"]

    );

}



// ===============================
// EXPORT RSA
// ===============================

async function exportPublicKey(key) {

    const spki =
        await crypto.subtle.exportKey(
            "spki",
            key
        );

    return bytesToBase64(
        new Uint8Array(spki)
    );

}


async function exportPrivateKey(key) {

    const pkcs8 =
        await crypto.subtle.exportKey(
            "pkcs8",
            key
        );

    return bytesToBase64(
        new Uint8Array(pkcs8)
    );

}



// ===============================
// IMPORT RSA
// ===============================

async function importPublicKey(base64) {

    return crypto.subtle.importKey(

        "spki",

        base64ToBytes(base64),

        {

            name: "RSA-OAEP",

            hash: "SHA-256"

        },

        true,

        ["encrypt"]

    );

}


async function importPrivateKey(base64) {

    return crypto.subtle.importKey(

        "pkcs8",

        base64ToBytes(base64),

        {

            name: "RSA-OAEP",

            hash: "SHA-256"

        },

        true,

        ["decrypt"]

    );

}



// ===============================
// RSA ENCRYPT / DECRYPT
// ===============================

async function encryptPEKWithPublicKey(
    rawPEK,
    publicKey
) {

    const encrypted =
        await crypto.subtle.encrypt(
            {

                name: "RSA-OAEP"

            },

            publicKey,

            rawPEK

        );

    return bytesToBase64(
        new Uint8Array(encrypted)
    );

}


async function decryptPEKWithPrivateKey(
    encryptedPEK,
    privateKey
) {

    return crypto.subtle.decrypt(

        {

            name: "RSA-OAEP"

        },

        privateKey,

        base64ToBytes(encryptedPEK)

    );

}
