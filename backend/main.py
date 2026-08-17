const fs = require("fs");
const path = require("path");
const readline = require("readline");
const { Client, PasteDBError } = require("./sdk");
const os = require("os");
const { execFileSync } = require("child_process");


const configDir = path.join(os.homedir(), ".pastedb");
const configFile = path.join(configDir, "config.json");

async function ask(question) {
    const rl = readline.createInterface({
        input: process.stdin,
        output: process.stdout
    });

    return new Promise(resolve => {
        rl.question(question, answer => {
            rl.close();
            resolve(answer.trim());
        });
    });
}
function formatDate(date) {
    if (!date) return "Unknown date";

    const d = new Date(date);

    if (isNaN(d.getTime())) {
        return String(date);
    }

    return d.toLocaleString();
}

function getPastePreview(paste) {
    const content =
        paste.content ||
        paste.text ||
        paste.description ||
        "";

    return String(content)
        .replace(/\s+/g, " ")
        .trim()
        .slice(0, 100);
}

function getPasteId(paste) {
    return (
        paste.custom_id||
        paste.paste_id ||
        paste.pasteId ||
        paste.custom_id ||
        paste._id
    );
}

function getPasteTitle(paste) {
    return paste.title || "Untitled";
}

function getPasteLanguage(paste) {
    return paste.syntax || "text";
}

function openUrl(url) {
    try {
        if (process.platform === "win32") {
            execFileSync("cmd", ["/c", "start", "", url]);
        } else if (process.platform === "darwin") {
            execFileSync("open", [url]);
        } else {
            execFileSync("xdg-open", [url]);
        }
    } catch {
        console.log("\nOpen this URL manually:");
        console.log(url);
    }
}
async function uploadTextPaste(content) {

    try {

        console.log("\nUploading text...");

        const data = await client.apiCreatePaste({
            title: "Untitled",
            content,
            language: "text",
            images: []
        });

        success("Text Uploaded!");

        // Try common URL fields returned by APIs
        const pasteId =
            data.id ||
            data.paste_id ||
            data.pasteId ||
            data.custom_id ||
            data.customId;

        if (data.url) {
            console.log(data.url);
        } else if (pasteId) {
            console.log(
                `https://pastedb.netlify.app/paste/${pasteId}`
            );
        } else {
            print(data);
            }

    } catch (err) {
        handleError(err);
    }
}

async function auth() {
    console.log("");
    console.log("PasteDB CLI Authentication");
    console.log("--------------------------");
    console.log("");

    const apiKey = await ask("PasteDB API key: ");

    if (!apiKey) {
        console.log("");
        console.log("✗ No API key provided.");
        return;
    }

    try {
        fs.mkdirSync(configDir, { recursive: true });

        fs.writeFileSync(
            configFile,
            JSON.stringify(
                {
                    apiKey: apiKey
                },
                null,
                2
            ),
            {
                mode: 0o600
            }
        );

        console.log("");
        console.log("✓ API key saved.");
        console.log("You can now use PasteDB CLI commands.");
        console.log("");

    } catch (err) {
        console.error("");
        console.error("✗ Failed to save API key.");
        console.error(err.message);
    }
                                 }



function getApiKey() {
    // Environment variable takes priority
    if (process.env.PASTEDB_API_KEY) {
        return process.env.PASTEDB_API_KEY;
    }

    try {
        const config = JSON.parse(
            fs.readFileSync(configFile, "utf8")
        );

        return config.apiKey || null;
    } catch {
        return null;
    }
}

const client = new Client(getApiKey());

// ─────────────────────────────────────────────
// Helpers
// ─────────────────────────────────────────────

function print(value) {
    if (typeof value === "string") {
        console.log(value);
    } else {
        console.log(JSON.stringify(value, null, 2));
    }
}

function error(message) {
    console.error(`\n✗ ${message}\n`);
    process.exitCode = 1;
}

function success(message) {
    console.log(`\n✓ ${message}\n`);
}

function getLanguage(filename) {
    const ext = path.extname(filename).toLowerCase();

    const languages = {
        ".js": "javascript",
        ".mjs": "javascript",
        ".cjs": "javascript",

        ".ts": "typescript",
        ".tsx": "typescript",

        ".py": "python",

        ".html": "html",
        ".htm": "html",

        ".css": "css",

        ".json": "json",

        ".md": "markdown",

        ".txt": "text",

        ".java": "java",
        ".c": "c",
        ".cpp": "cpp",
        ".h": "c",

        ".cs": "csharp",

        ".go": "go",
        ".rs": "rust",

        ".php": "php",
        ".rb": "ruby",

        ".sh": "bash",
        ".bash": "bash",

        ".sql": "sql",

        ".xml": "xml",

        ".yaml": "yaml",
        ".yml": "yaml"
    };

    return languages[ext] || "text";
}
async function pastes() {

    let data;

    try {
        console.log("\nFetching your pastes...\n");

        data = await client.apiUserPastes();
if (typeof data === "string") {
    try {
        data = JSON.parse(data);
    } catch {
        console.log("API returned invalid JSON.");
        console.log(data);
        return;
    }
}
    } catch (err) {
        handleError(err);
        return;
    }

    // Handle different possible API response formats
    let pastesList;

    if (Array.isArray(data.results)) {
        pastesList = data.results;
     } else {
        console.log("Unexpected API response:\n");
       print(Array.isArray(data.results))
print(typeof data.results)
        return;
}

    if (pastesList.length === 0) {
        console.log("┌──────────────────────────────────────┐");
        console.log("│              PasteDB                 │");
        console.log("├──────────────────────────────────────┤");
        console.log("│ You don't have any pastes yet.       │");
        console.log("│                                      │");
        console.log("│ Create one with:                     │");
        console.log("│   pdb create <file>                  │");
        console.log("└──────────────────────────────────────┘\n");
        return;
    }

    let selected = 0;
    let filtered = [...pastesList];
    let searchMode = false;
    let searchText = "";

    function applySearch() {

        const query = searchText.toLowerCase().trim();

        if (!query) {
            filtered = [...pastesList];
            return;
        }

        filtered = pastesList.filter(paste => {

            const title = getPasteTitle(paste).toLowerCase();
            const id = String(getPasteId(paste) || "").toLowerCase();
            const language = getPasteLanguage(paste).toLowerCase();
            const content = String(paste.content || "").toLowerCase();

            return (
                title.includes(query) ||
                id.includes(query) ||
                language.includes(query) ||
                content.includes(query)
            );
        });
    }

    function render() {

        console.clear();

        console.log("╭──────────────────────────────────────────────────────────────╮");
        console.log("│                         PasteDB                              │");
        console.log("│                       Your Pastes                            │");
        console.log("╰──────────────────────────────────────────────────────────────╯");

        console.log(
            `\n  ${filtered.length} paste${filtered.length === 1 ? "" : "s"}`
        );

        if (searchText) {
            console.log(`  Search: "${searchText}"`);
        }

        console.log("");

        if (filtered.length === 0) {
            console.log("  No pastes found.");
        }

        filtered.forEach((paste, index) => {

            const id = getPasteId(paste);
            const title = getPasteTitle(paste);
            const language = getPasteLanguage(paste);
            const preview = getPastePreview(paste);

            const created =
                paste.created_at ||
                paste.createdAt ||
                paste.date;

            const isSelected = index === selected;

            console.log(
                isSelected
                    ? `  ❯ ${title}`
                    : `    ${title}`
            );

            console.log(
                `      ID:       ${id || "unknown"}`
            );

            console.log(
                `      Language: ${language}`
            );

            if (preview) {
                console.log(
                    `      Preview:  ${preview}`
                );
            }

            console.log("");
        });

        console.log(
            "──────────────────────────────────────────────────────────────"
        );

        console.log(
            "↑ ↓ Navigate   Ctrl+Enter Open   d Delete   / Search   r Refresh   q Quit"
        );
    }

    async function deleteSelected() {

        const paste = filtered[selected];

        if (!paste) return;

        const id = getPasteId(paste);

        if (!id) {
            console.log("\nCannot determine paste ID.");
            return;
        }

        const title = getPasteTitle(paste);

        process.stdin.setRawMode(false);

        console.log(
            `\nDelete "${title}" (${id})?`
        );

        const answer = await ask(
            "Type 'yes' to confirm: "
        );

        if (answer.toLowerCase() !== "yes") {
            console.log("\nCancelled.");
            return;
        }

        try {

            await client.apiDeletePaste(id);

            console.log("\n✓ Paste deleted.");

            pastesList = pastesList.filter(
                p => getPasteId(p) !== id
            );

            applySearch();

            if (selected >= filtered.length) {
                selected = Math.max(0, filtered.length - 1);
            }

        } catch (err) {
            console.log("\n✗ Failed to delete paste.");
            console.log(err.message);
        }
    }

    async function search() {

        process.stdin.setRawMode(false);

        const query = await ask(
            "\nSearch pastes: "
        );

        searchText = query;

        applySearch();
        selected = 0;
    }

    render();

    readline.emitKeypressEvents(process.stdin);
    process.stdin.setRawMode(true);

    return new Promise(resolve => {

        const onKeypress = async (_, key) => {

            if (!key) return;

            // Ctrl+C
            if (
                key.ctrl &&
                key.name === "c"
            ) {
                process.stdin.setRawMode(false);
                process.stdin.removeListener(
                    "keypress",
                    onKeypress
                );
                console.clear();
                resolve();
                return;
            }

            // Quit
            if (key.name === "q") {

                process.stdin.setRawMode(false);

                process.stdin.removeListener(
                    "keypress",
                    onKeypress
                );

                console.clear();

                resolve();
                return;
            }

            // Up
            if (key.name === "up") {

                if (filtered.length > 0) {
                    selected =
                        selected <= 0
                            ? filtered.length - 1
                            : selected - 1;
                }

                render();
                return;
            }

            // Down
            if (key.name === "down") {

                if (filtered.length > 0) {
                    selected =
                        selected >= filtered.length - 1
                            ? 0
                            : selected + 1;
                }

                render();
                return;
            }

            // Open
            if (key.name === "o" || key.sequence === "o") {

                const paste = filtered[selected];

                if (!paste) return;

                const id = getPasteId(paste);

                if (!id) return;

                const url =
                    `https://pastedb.netlify.app/paste/${id}`;

                process.stdin.setRawMode(false);

                console.log(`\nOpening ${url}...\n`);

                openUrl(url);

                setTimeout(() => {
                    process.stdin.setRawMode(true);
                    render();
                }, 500);

                return;
            }

            // Delete
            if (key.name === "d") {

                await deleteSelected();

                if (filtered.length > 0) {
                    process.stdin.setRawMode(true);
                }

                render();

                return;
            }

            // Search
            if (key.sequence === "/" || key.name === "/") {

                await search();

                process.stdin.setRawMode(true);

                render();

                return;
            }

            // Refresh
            if (key.name === "r") {

                process.stdin.setRawMode(false);

                try {

                    console.clear();

                    console.log(
                        "\nRefreshing your pastes...\n"
                    );

                    const fresh =
                        await client.apiUserPastes();

                    if (Array.isArray(fresh)) {
                        pastesList = fresh;
                    } else if (Array.isArray(fresh.pastes)) {
                        pastesList = fresh.pastes;
                    } else if (Array.isArray(fresh.data)) {
                        pastesList = fresh.data;
                    }

                    applySearch();

                    selected = 0;

                } catch (err) {

                    console.log(
                        `\n✗ ${err.message}`
                    );
                }

                process.stdin.setRawMode(true);

                render();

                return;
            }
        };

        process.stdin.on(
            "keypress",
            onKeypress
        );
    });
        }
async function getClipboardText() {
    try {
        // Android / Termux
        if (process.platform === "android" || fs.existsSync("/data/data/com.termux")) {
            return execFileSync(
                "termux-clipboard-get",
                { encoding: "utf8" }
            );
        }

        // macOS
        if (process.platform === "darwin") {
            return execFileSync(
                "pbpaste",
                { encoding: "utf8" }
            );
        }

        // Windows
        if (process.platform === "win32") {
            return execFileSync(
                "powershell",
                [
                    "-NoProfile",
                    "-Command",
                    "Get-Clipboard"
                ],
                { encoding: "utf8" }
            );
        }

        // Linux
        try {
            return execFileSync(
                "xclip",
                ["-selection", "clipboard", "-o"],
                { encoding: "utf8" }
            );
        } catch {}

        try {
            return execFileSync(
                "xsel",
                ["--clipboard", "--output"],
                { encoding: "utf8" }
            );
        } catch {}

        throw new Error("Clipboard access is not available.");
    } catch (err) {
        throw new Error(
            "Could not read clipboard. " +
            "On Termux, install Termux:API and run: " +
            "pkg install termux-api"
        );
    }
}


async function chooseCreateSource() {

    console.log("");
    console.log("What do you want to upload?");
    console.log("");
    console.log("  1) File");
    console.log("  2) Raw text");
    console.log("  3) Clipboard");
    console.log("");

    const choice = await ask("Choose an option [1-3]: ");

    if (choice === "1") {

        const file = await ask(
            "\nWhich file do you want to upload?\n> "
        );

        if (!file) {
            error("No file specified.");
            return;
        }

        return {
            type: "file",
            value: file
        };
    }

    if (choice === "2") {

        console.log("");
        console.log("Enter the text you want to upload.");
        console.log("Press Ctrl+D when finished.");
        console.log("");

        const lines = [];

        const rl = readline.createInterface({
            input: process.stdin,
            output: process.stdout
        });

        for await (const line of rl) {
            lines.push(line);
        }

        rl.close();

        const text = lines.join("\n");

        if (!text.trim()) {
            error("No text entered.");
            return;
        }

        return {
            type: "text",
            value: text
        };
    }

    if (choice === "3") {

        let clipboard;

        try {
            clipboard = await getClipboardText();
        } catch (err) {
            error(err.message);
            return;
        }

        if (!clipboard.trim()) {
            error("Clipboard is empty.");
            return;
        }

        console.log("");
        console.log("Clipboard snapshot:");
        console.log("");
        console.log("────────────────────────────────");

        console.log(clipboard);

        console.log("────────────────────────────────");
        console.log("");

        const confirm = await ask(
            "Press Enter to upload this clipboard content, or type 'n' to cancel: "
        );

        if (confirm.toLowerCase() === "n") {
            console.log("\nCancelled.\n");
            return;
        }

        return {
            type: "text",
            value: clipboard
        };
    }

    error("Invalid option. Please choose 1, 2, or 3.");
}


// ─────────────────────────────────────────────
// Commands
// ─────────────────────────────────────────────

async function createPaste(file) {

    // ==========================================
    // INTERACTIVE MODE
    // ==========================================

    if (!file) {

        const source = await chooseCreateSource();

        if (!source) {
            return;
        }

        // File selected
        if (source.type === "file") {
            return createPaste(source.value);
        }

        // Raw text / clipboard
        return uploadTextPaste(source.value);
    }


    // ==========================================
    // NORMAL FILE MODE
    // pdb create app.js
    // ==========================================

    if (!fs.existsSync(file)) {
        return error(`File not found: ${file}`);
    }

    if (!fs.statSync(file).isFile()) {
        return error(`${file} is not a file.`);
    }

    try {

        console.log(`\nUploading ${file}...`);

        const content = fs.readFileSync(file, "utf8");

        const language = getLanguage(file);

        const title = path.basename(file);

        const data = await client.apiCreatePaste({
            title,
            content,
            language,
            images: []
        });

        success("Paste created!");

        // Try common URL fields returned by APIs
        const pasteId =
            data.id ||
            data.paste_id ||
            data.pasteId ||
            data.custom_id ||
            data.customId;

        if (data.url) {
            console.log(data.url);
        } else if (pasteId) {
            console.log(
                `https://pastedb.netlify.app/paste/${pasteId}`
            );
        } else {
            print(data);
                }

    } catch (err) {
        handleError(err);
    }
}
async function getPaste(id) {

    if (!id) {
        return error("Please provide a paste ID.\nExample: pdb get abc123");
    }

    try {

        console.log(`\nFetching ${id}...`);

        const data = await client.apiGetPaste(id);

        console.log();

        if (typeof data.content === "string") {
            console.log(data.content);
        } else {
            print(data);
        }

    } catch (err) {
        handleError(err);
    }
}


async function deletePaste(id) {

    if (!id) {
        return error("Please provide a paste ID.\nExample: pdb delete abc123");
    }

    try {

        console.log(`\nDeleting ${id}...`);

        await client.apiDeletePaste(id);

        success("Paste deleted.");

    } catch (err) {
        handleError(err);
    }
}


async function updatePaste(id, file) {

    if (!id || !file) {
        return error(
            "Usage:\n  pdb update <paste-id> <file>"
        );
    }

    if (!fs.existsSync(file)) {
        return error(`File not found: ${file}`);
    }

    try {

        console.log(`\nUpdating ${id}...`);

        const content = fs.readFileSync(file, "utf8");

        const language = getLanguage(file);

        const data = await client.apiUpdatePaste(id, {
            content,
            language,
            title: path.basename(file)
        });

        success("Paste updated.");

        print(data);

    } catch (err) {
        handleError(err);
    }
}



async function explore() {

    try {

        console.log("\nFetching public pastes...\n");

        const data = await client.explore();

        print(data);

    } catch (err) {
        handleError(err);
    }
}


async function me() {

    try {

        const data = await client.apiMe();

        console.log("\nAccount:\n");

        print(data);

    } catch (err) {
        handleError(err);
    }
}


async function runCode(language, file) {

    if (!language || !file) {
        return error(
            "Usage:\n  pdb run <language> <file>\n\n" +
            "Example:\n  pdb run python app.py"
        );
    }

    if (!fs.existsSync(file)) {
        return error(`File not found: ${file}`);
    }

    try {

        const code = fs.readFileSync(file, "utf8");

        console.log(`\nRunning ${file}...\n`);

        const result = await client.runCode(
            language,
            code
        );

        print(result);

    } catch (err) {
        handleError(err);
    }
}


async function checkId(id) {

    if (!id) {
        return error(
            "Usage:\n  pdb check-id <custom-id>"
        );
    }

    try {

        const data = await client.checkCustomId(id);

        print(data);

    } catch (err) {
        handleError(err);
    }
}


// ─────────────────────────────────────────────
// API key commands
// ─────────────────────────────────────────────

async function generateKey(name) {

    if (!name) {
        return error(
            "Usage:\n  pdb key create <name>"
        );
    }

    try {

        const data = await client.generateApiKey(name);

        success("API key created.");

        print(data);

    } catch (err) {
        handleError(err);
    }
}


async function listKeys() {

    try {

        const data = await client.myApiKeys();

        print(data);

    } catch (err) {
        handleError(err);
    }
}


async function deleteKey(key) {

    if (!key) {
        return error(
            "Usage:\n  pdb key delete <api-key>"
        );
    }

    try {

        await client.deleteApiKey(key);

        success("API key deleted.");

    } catch (err) {
        handleError(err);
    }
}


// ─────────────────────────────────────────────
// Help
// ─────────────────────────────────────────────

function showHelp() {

    console.log(`
PasteDB CLI

Usage:
  pdb <command> [arguments]

Commands:

  create <file>
      Create a paste from a local file

      Example:
        pdb create app.py

  pastes
      Browse all your PasteDB pastes interactively

      Controls:
        ↑ ↓        Navigate(Up and Down Arrow)
        O.         Open paste
        /          Search
        d          Delete
        r          Refresh
        q          Quit


  get <id>
      Get a paste

      Example:
        pdb get abc123


  update <id> <file>
      Update an existing paste

      Example:
        pdb update abc123 app.py


  delete <id>
      Delete a paste

      Example:
        pdb delete abc123


  explore
      Explore public pastes


  me
      Show your PasteDB account


  run <language> <file>
      Run code using PasteDB

      Example:
        pdb run python app.py


  check-id <id>
      Check whether a custom paste ID is available

      Example:
        pdb check-id my-project


API Keys:

  pdb key create <name>
      Generate an API key

  pdb key list
      List your API keys

  pdb key delete <key>
      Delete an API key


Other:

  pdb help
      Show this help

  pdb version
      Show CLI version
`);
}


function showVersion() {
    console.log("PasteDB CLI v0.1.8 by Aditya Sorathiya");
}


// ─────────────────────────────────────────────
// Error handling
// ─────────────────────────────────────────────

function handleError(err) {

    if (err instanceof PasteDBError) {
        error(err.message);
        return;
    }

    if (err.code === "ENOENT") {
        error("File not found.");
        return;
    }

    if (err.name === "AbortError") {
        error("Request timed out.");
        return;
    }

    error(
        err.message ||
        "Something went wrong."
    );
}


// ─────────────────────────────────────────────
// CLI Router
// ─────────────────────────────────────────────

async function main() {

    const args = process.argv.slice(2);

    const command = args[0];

    switch (command) {

        case "create":
            await createPaste(args[1]);
            break;

        case "auth":
            await auth();
            break;

        case "pastes":
            await pastes();
            break;

        case "get":
            await getPaste(args[1]);
            break;

        case "update":
            await updatePaste(args[1], args[2]);
            break;

        case "delete":
            await deletePaste(args[1]);
            break;

        case "stats":
            await stats(args[1]);
            break;

        case "explore":
            await explore();
            break;

        case "me":
            await me();
            break;

        case "run":
            await runCode(args[1], args[2]);
            break;

        case "check-id":
            await checkId(args[1]);
            break;

        case "key":

            switch (args[1]) {

                case "create":
                    await generateKey(args.slice(2).join(" "));
                    break;

                case "list":
                    await listKeys();
                    break;

                case "delete":
                    await deleteKey(args[2]);
                    break;

                default:
                    console.log(`
API key commands:

  pdb key create <name>
  pdb key list
  pdb key delete <key>
`);
            }

            break;

        case "version":
        case "-v":
        case "--version":
            showVersion();
            break;

        case "help":
        case "-h":
        case "--help":
        case undefined:
            showHelp();
            break;

        default:
            error(
                `Unknown command "${command}".\n` +
                `Run "pdb help" to see available commands.`
            );
    }
}


main();
