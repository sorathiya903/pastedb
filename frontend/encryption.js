// Creates and stores a master key if one doesn't exist.
async function makeMasterKey() {

    const key = await crypto.subtle.generateKey(
        {
            name: "AES-GCM",
            length: 256
        },
        true,
        ["encrypt", "decrypt"]
    );

    const raw = await crypto.subtle.exportKey(
        "raw",
        key
    );

    const b64 = btoa(
        String.fromCharCode(...new Uint8Array(raw))
    );

    localStorage.setItem(
        "masterKey",
        b64
    );

    return key;
}

async function getMasterKey(){

    let stored =
        localStorage.getItem("masterKey");

    if(!stored){

        return await makeMasterKey();

    }

    const bytes = Uint8Array.from(
        atob(stored),
        c => c.charCodeAt(0)
    );

    return await crypto.subtle.importKey(
        "raw",
        bytes,
        "AES-GCM",
        true,
        ["encrypt","decrypt"]
    );
}



async function generatePEK(){

    return await crypto.subtle.generateKey(
        {
            name:"AES-GCM",
            length:256
        },
        true,
        ["encrypt","decrypt"]
    );

}


  async function encryptPasteData(pasteData){

    const masterKey =
        await getMasterKey();

    const pek =
        await generatePEK();

    const encryptedTitle =
        await encryptWithKey(
            pasteData.title,
            pek
        );

    const encryptedContent =
        await encryptWithKey(
            pasteData.content,
            pek
        );

    const encryptedImages =
        await Promise.all(

            pasteData.images.map(url =>
                encryptWithKey(url, pek)
            )

        );

    const rawPEK =
        await crypto.subtle.exportKey(
            "raw",
            pek
        );

    const encryptedPEK =
        await encryptRawKey(
            rawPEK,
            masterKey
        );

    return {

        ...pasteData,

        title: encryptedTitle,

        content: encryptedContent,

        images: encryptedImages,

        encrypted_pek: encryptedPEK

    };

}


async function encryptWithKey(text, key){

    const iv = crypto.getRandomValues(
        new Uint8Array(12)
    );

    const encoded = new TextEncoder().encode(text);

    const encrypted =
        await crypto.subtle.encrypt(
            {
                name: "AES-GCM",
                iv
            },
            key,
            encoded
        );

    return {
        iv: btoa(String.fromCharCode(...iv)),
        data: btoa(
            String.fromCharCode(
                ...new Uint8Array(encrypted)
            )
        )
    };

}


async function decryptWithKey(obj, key){

    const iv = Uint8Array.from(
        atob(obj.iv),
        c => c.charCodeAt(0)
    );

    const data = Uint8Array.from(
        atob(obj.data),
        c => c.charCodeAt(0)
    );

    const decrypted =
        await crypto.subtle.decrypt(
            {
                name: "AES-GCM",
                iv
            },
            key,
            data
        );

    return new TextDecoder().decode(decrypted);

}


async function encryptRawKey(rawPEK, masterKey){

    const iv = crypto.getRandomValues(
        new Uint8Array(12)
    );

    const encrypted =
        await crypto.subtle.encrypt(
            {
                name: "AES-GCM",
                iv
            },
            masterKey,
            rawPEK
        );

    return {
        iv: btoa(String.fromCharCode(...iv)),
        data: btoa(
            String.fromCharCode(
                ...new Uint8Array(encrypted)
            )
        )
    };

        }


async function decryptRawKey(obj){

    const masterKey =
        await getMasterKey();

    const iv = Uint8Array.from(
        atob(obj.iv),
        c => c.charCodeAt(0)
    );

    const data = Uint8Array.from(
        atob(obj.data),
        c => c.charCodeAt(0)
    );

    const rawPEK =
        await crypto.subtle.decrypt(
            {
                name: "AES-GCM",
                iv
            },
            masterKey,
            data
        );

    return await crypto.subtle.importKey(
        "raw",
        rawPEK,
        "AES-GCM",
        true,
        ["encrypt", "decrypt"]
    );

}
