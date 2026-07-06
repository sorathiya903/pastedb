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
async function decryptPasteWithSharedPEK(paste, rawPEKBase64) {

    const pek = await importAESKey(rawPEKBase64);

    return {
        ...paste,

        title: await decryptWithAES(paste.title, pek),

        content: await decryptWithAES(paste.content, pek),

        images: await Promise.all(
            (paste.images || []).map(img =>
                decryptWithAES(img, pek)
            )
        ),

        _pek: pek
    };
}

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



async function encryptPasteData(pasteData, existingPEK = null, useAccountKEK=true) {

    const pek = existingPEK || await generatePEK();

    const accountKEK = useAccountKEK
    ? await getFromDB("accountKEK")
    : null;
    const rawPEK = await crypto.subtle.exportKey("raw", pek);

    const rawPEKBase64 =
        bytesToBase64(new Uint8Array(rawPEK));

    sharePEK = rawPEKBase64;

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

    const result = {

        ...pasteData,

        title: encryptedTitle,

        content: encryptedContent,

        images: encryptedImages,
        guest:false

    };

    if (useAccountKEK && accountKEK) {
    result.encrypted_pek = await encryptWithAES(
        rawPEKBase64,
        accountKEK
    );
}
     result.guest = !useAccountKEK;

    return result;
}

async function decryptPasteData(paste) {

    let rawPEKBase64;

    const accountKEK =
        await getFromDB("accountKEK");

    if (accountKEK && paste.encrypted_pek) {

        rawPEKBase64 =
            await decryptWithAES(
                paste.encrypted_pek,
                accountKEK
            );

    } else {

        rawPEKBase64 =
            decodeURIComponent(
                location.hash.substring(1)
            );

        if (!rawPEKBase64) {
            throw new Error("Missing PEK in URL.");
        }

    }

    const pek =
        await importAESKey(rawPEKBase64);

    const decrypted = {
        ...paste
    };

    if (paste.title) {
        decrypted.title =
            await decryptWithAES(
                paste.title,
                pek
            );
    }

    if (paste.content) {
        decrypted.content =
            await decryptWithAES(
                paste.content,
                pek
            );
    }

    if (Array.isArray(paste.images)) {
        decrypted.images =
            await Promise.all(
                paste.images.map(img =>
                    decryptWithAES(img, pek)
                )
            );
    }

    decrypted._pek = pek;

    return decrypted;
        }
