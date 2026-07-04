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


// ===============================
// INDEXED DB
// ===============================

const DB_NAME = "PasteDBCrypto";
const STORE_NAME = "keys";
const DB_VERSION = 1;

function openCryptoDB() {

    return new Promise((resolve, reject) => {

        const request = indexedDB.open(
            DB_NAME,
            DB_VERSION
        );

        request.onupgradeneeded = () => {

            const db = request.result;

            if (!db.objectStoreNames.contains(STORE_NAME)) {

                db.createObjectStore(STORE_NAME);

            }

        };

        request.onsuccess = () => {

            resolve(request.result);

        };

        request.onerror = () => {

            reject(request.error);

        };

    });

        }


async function saveToDB(key, value) {

    const db = await openCryptoDB();

    return new Promise((resolve, reject) => {

        const tx = db.transaction(
            STORE_NAME,
            "readwrite"
        );

        tx.objectStore(STORE_NAME)
            .put(value, key);

        tx.oncomplete = () => resolve();

        tx.onerror = () => reject(tx.error);

    });

            }


async function deleteFromDB(key) {

    const db = await openCryptoDB();

    return new Promise((resolve, reject) => {

        const tx = db.transaction(
            STORE_NAME,
            "readwrite"
        );

        tx.objectStore(STORE_NAME)
            .delete(key);

        tx.oncomplete = () => resolve();

        tx.onerror = () => reject(tx.error);

    });

}

  async function getFromDB(key) {

    const db = await openCryptoDB();

    return new Promise((resolve, reject) => {

        const tx = db.transaction(
            STORE_NAME,
            "readonly"
        );

        const req =
            tx.objectStore(STORE_NAME)
            .get(key);

        req.onsuccess = () => {

            resolve(req.result);

        };

        req.onerror = () => {

            reject(req.error);

        };

    });

                       }



async function clearCryptoDB() {

    const db = await openCryptoDB();

    return new Promise((resolve, reject) => {

        const tx = db.transaction(
            STORE_NAME,
            "readwrite"
        );

        tx.objectStore(STORE_NAME)
            .clear();

        tx.oncomplete = () => resolve();

        tx.onerror = () => reject(tx.error);

    });

    }


async function ensureDeviceKeys() {

    let privateKey = await getFromDB("privateKey");
    let publicKey = await getFromDB("publicKey");
    let deviceId = await getFromDB("deviceId");

    if (privateKey && publicKey && deviceId) {

        return {
            privateKey,
            publicKey,
            deviceId
        };

    }

    const pair = await generateRSAKeyPair();

    deviceId = crypto.randomUUID();

    await saveToDB("privateKey", pair.privateKey);
    await saveToDB("publicKey", pair.publicKey);
    await saveToDB("deviceId", deviceId);

    return {
        privateKey: pair.privateKey,
        publicKey: pair.publicKey,
        deviceId
    };

        }



async function encryptPasteData(pasteData, existingPEK = null) {

    // Generate one PEK for this paste
    const pek = existingPEK || await generatePEK();


    // Encrypt paste
    const encryptedTitle =
        await encryptWithAES(
            pasteData.title,
            pek
        );

    const encryptedContent =
        await encryptWithAES(
            pasteData.content,
            pek
        );

    const encryptedImages =
        await Promise.all(
            (pasteData.images || []).map(img =>
                encryptWithAES(img, pek)
            )
        );

    // Export raw PEK
    const rawPEK =
        await crypto.subtle.exportKey(
            "raw",
            pek
        );

    // Get approved devices
    const res =
        await fetch(
            "/device/keys",
            {
                credentials: "include"
            }
        );

    const json =
        await res.json();

    const encryptedPEKs = {};

    // Encrypt PEK for every device
    for (const device of json.devices) {

        const publicKey =
            await importPublicKey(
                device.public_key
            );

        encryptedPEKs[
            device.device_id
        ] =
        await encryptPEKWithPublicKey(
            rawPEK,
            publicKey
        );

    }

    return {

        ...pasteData,

        title: encryptedTitle,

        content: encryptedContent,

        images: encryptedImages,

        encrypted_peks:
            encryptedPEKs

    };

}

async function decryptPasteData(paste) {

    const privateKey =
        await getFromDB("privateKey");

    const deviceId =
        await getFromDB("deviceId");

    if (!privateKey || !deviceId) {
        throw new Error("Device keys not found.");
    }

    const encryptedPEK =
        paste.encrypted_peks?.[deviceId];

    if (!encryptedPEK) {
        throw new Error(
            "This device cannot decrypt this paste."
        );
    }

    const rawPEK =
        await decryptPEKWithPrivateKey(
            encryptedPEK,
            privateKey
        );

    const pek =
        await crypto.subtle.importKey(
            "raw",
            rawPEK,
            "AES-GCM",
            true,
            ["encrypt", "decrypt"]
        );

    const decrypted = {
        ...paste
    };

    decrypted.title =
        await decryptWithAES(
            paste.title,
            pek
        );

    decrypted.content =
        await decryptWithAES(
            paste.content,
            pek
        );

    decrypted.images =
        await Promise.all(
            (paste.images || []).map(img =>
                decryptWithAES(img, pek)
            )
        );

    decrypted._pek = pek;

return decrypted;
                }
