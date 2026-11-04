
/*
 * PasteDB Security Scanner
 *
 * Layer 1: Known credential patterns and context rules
 * Layer 2: Random / high-entropy string detection
 *
 * Main function: checkSecrets()
 */

const KEY_IDENTIFIERS_URL = "/key-identify.json";

// -------------------------------
// Configuration
// -------------------------------

const SCANNER_CONFIG = {
    minEntropyLength: 20,
    minEntropy: 3.5,
    debounce: 0,
    hideValues: true
};

// -------------------------------
// Load identifier database
// -------------------------------

let identifierDatabase = null;

async function loadKeyIdentifiers() {
    
    

    const response = await fetch(KEY_IDENTIFIERS_URL, {
        cache: "no-cache"
    });

    console.log("Scanner config status:", response.status);
    console.log("Scanner config URL:", response.url);
    console.log("Scanner config content type:",
        response.headers.get("content-type")
    );

    const raw = await response.text();

    console.log("Scanner config response:", raw.slice(0, 500));

    if (!response.ok) {
        throw new Error(
            `Could not load key-identify.json: HTTP ${response.status}`
        );
    }

    try {
        keyIdentifiersCache = JSON.parse(raw);
    } catch (error) {
        throw new Error(
            `key-identify.json contains invalid JSON: ${error.message}`
        );
    }

    return keyIdentifiersCache;
}

// -------------------------------
// Utility functions
// -------------------------------

function getLineNumber(content, index) {
    return content.slice(0, index).split("\n").length;
}

function getNearbyContext(content, index, length = 100) {
    return content.slice(
        Math.max(0, index - length),
        Math.min(content.length, index + length)
    ).toUpperCase();
}

function hasKeyword(context, keywords = []) {
    return keywords.some(keyword =>
        context.includes(keyword.toUpperCase())
    );
}

function addFinding(findings, finding) {
    const duplicate = findings.some(item =>
        item.start === finding.start &&
        item.end === finding.end
    );

    if (!duplicate) findings.push(finding);
}

// -------------------------------
// Layer 1: Known secret detection
// -------------------------------

function scanKnownSecrets(content, database) {
    const findings = [];

    for (const provider of database.providers || []) {
        for (const credential of provider.credentials || []) {

            for (const prefix of credential.prefixes || []) {
                let searchFrom = 0;

                while (true) {
                    const index = content.indexOf(prefix, searchFrom);

                    if (index === -1) break;

                    searchFrom = index + prefix.length;

                    // Extract candidate token.
                    const match = content
                        .slice(index)
                        .match(/^[A-Za-z0-9_\-./+=:]+/);

                    if (!match) continue;

                    const value = match[0];

                    if (value.length < (credential.minimum_length || 8)) {
                        continue;
                    }

                    const context = getNearbyContext(content, index);

                    if (
                        credential.requires_context &&
                        !hasKeyword(context, credential.context_keywords)
                    ) {
                        continue;
                    }

                    if (
                        credential.requires_structure &&
                        credential.id === "jwt" &&
                        value.split(".").length !== 3
                    ) {
                        continue;
                    }

                    addFinding(findings, {
                        id: credential.id,
                        provider: provider.name,
                        type: credential.name,
                        severity: credential.severity || "high",
                        confidence: "high",
                        line: getLineNumber(content, index),
                        start: index,
                        end: index + value.length,
                        message: `${credential.name} pattern detected`
                    });
                }
            }
        }
    }

    // Context-only rules.
    for (const rule of database.context_rules || []) {
        for (const keyword of rule.keywords || []) {
            const regex = new RegExp(
                `\\b${escapeRegex(keyword)}\\b`,
                "gi"
            );

            let match;

            while ((match = regex.exec(content)) !== null) {
                const index = match.index;
                const afterKeyword = content.slice(
                    index + match[0].length,
                    index + match[0].length + 300
                );

                // Look for an assignment and a non-empty value.
                const assignment = afterKeyword.match(
                    /^\s*(?:[:=]|=>)\s*["'`]?([^\s"'`,;}]+)/ 
                );

                if (!assignment) continue;

                const value = assignment[1];

                if (!value || value.length < 4) continue;

                const valueIndex =
                    index + match[0].length +
                    afterKeyword.indexOf(assignment[0]) +
                    assignment[0].indexOf(assignment[1]);

                addFinding(findings, {
                    id: rule.id,
                    provider: "Generic",
                    type: rule.name,
                    severity: rule.severity || "medium",
                    confidence: "medium",
                    line: getLineNumber(content, valueIndex),
                    start: valueIndex,
                    end: valueIndex + value.length,
                    message: `${rule.name} found in assignment`
                });
            }
        }
    }

    return findings;
}

function escapeRegex(value) {
    return value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

// -------------------------------
// Layer 2: Entropy detection
// -------------------------------

function calculateEntropy(value) {
    const frequencies = {};

    for (const character of value) {
        frequencies[character] =
            (frequencies[character] || 0) + 1;
    }

    let entropy = 0;

    for (const count of Object.values(frequencies)) {
        const probability = count / value.length;

        entropy -= probability * Math.log2(probability);
    }

    return entropy;
}

function scanRandomStrings(content, knownFindings, database) {
    const findings = [];

    /*
     * Candidate strings:
     * - Quoted strings
     * - Backtick strings
     * - Long unquoted values after assignments
     */

    const regex = /["'`]([A-Za-z0-9+/_=.-]{20,})["'`]|(?:=|:)\s*([A-Za-z0-9+/_=-]{20,})/g;

    let match;

    while ((match = regex.exec(content)) !== null) {
        const value = match[1] || match[2];

        if (!value) continue;

        const start = match.index + match[0].indexOf(value);
        const end = start + value.length;

        // Skip anything already identified by Layer 1.
        const alreadyDetected = knownFindings.some(item =>
            start < item.end && end > item.start
        );

        if (alreadyDetected) continue;

        // Avoid common non-secret patterns.
        if (/^[0-9a-f]{8}-[0-9a-f-]{27,}$/i.test(value)) continue;
        if (/^[0-9a-f]{40,}$/i.test(value)) continue;

        const entropy = calculateEntropy(value);

        const uniqueCharacters = new Set(value).size;

        if (
            value.length >= SCANNER_CONFIG.minEntropyLength &&
            entropy >= SCANNER_CONFIG.minEntropy &&
            uniqueCharacters >= 10
        ) {
            const context = getNearbyContext(content, start);

            const keywords = (
                database.context_rules || []
            ).flatMap(rule => rule.keywords || []);

            const contextual = hasKeyword(context, keywords);

            findings.push({
                id: "random-secret",
                provider: "Unknown",
                type: contextual
                    ? "Possible API key or secret"
                    : "Unusual random string",
                severity: contextual ? "high" : "medium",
                confidence: contextual ? "medium" : "low",
                line: getLineNumber(content, start),
                start,
                end,
                entropy: entropy.toFixed(2),
                message: "A random-looking string was detected"
            });
        }
    }

    return findings;
}

// -------------------------------
// Main scanning function
// -------------------------------

async function scanSecrets(content) {
    const database = await loadKeyIdentifiers();

    const knownFindings = scanKnownSecrets(content, database);

    const randomFindings = scanRandomStrings(
        content,
        knownFindings,
        database
    );

    return [...knownFindings, ...randomFindings]
        .sort((a, b) => a.start - b.start);
}

// -------------------------------
// Warning modal
// -------------------------------

function showSecretWarning(findings) {
    const existing = document.getElementById("pastedb-secret-warning");

    if (existing) existing.remove();

    const modal = document.createElement("div");

    modal.id = "pastedb-secret-warning";

    modal.innerHTML = `
        <div class="pdb-secret-overlay">
            <div class="pdb-secret-modal">

                <div class="pdb-secret-heading">
                    <span class="pdb-secret-icon">⚠</span>
                    <div>
                        <h2>Potential secrets detected</h2>
                        <p>Review your content before sharing it.</p>
                    </div>
                </div>

                <div class="pdb-secret-list">
                    ${findings.map(item => `
                        <div class="pdb-secret-item">
                            <div>
                                <strong>${escapeHTML(item.type)}</strong>
                                <p>
                                    Line ${item.line} ·
                                    ${escapeHTML(item.confidence)} confidence
                                </p>
                            </div>
                            <span class="pdb-secret-severity">
                                ${escapeHTML(item.severity)}
                            </span>
                        </div>
                    `).join("")}
                </div>

                <div class="pdb-secret-privacy">
                    🔒 Scanned locally in your browser.
                    Detected values are hidden.
                </div>

                <div class="pdb-secret-actions">
                    <button id="pdb-secret-review">
                        Go back and review
                    </button>
                    <button id="pdb-secret-continue">
                        Continue anyway
                    </button>
                </div>

            </div>
        </div>
    `;

    document.body.appendChild(modal);

    return new Promise(resolve => {
        modal.querySelector("#pdb-secret-review").onclick = () => {
            modal.remove();
            resolve(false);
        };

        modal.querySelector("#pdb-secret-continue").onclick = () => {
            modal.remove();
            resolve(true);
        };
    });
}

function escapeHTML(value) {
    return String(value).replace(/[&<>"']/g, character => ({
        "&": "&amp;",
        "<": "&lt;",
        ">": "&gt;",
        '"': "&quot;",
        "'": "&#039;"
    })[character]);
}

// -------------------------------
// Public function
// Call before creating a paste.
// -------------------------------

async function checkSecrets(content) {
    try {
        const findings = await scanSecrets(content);

        if (findings.length === 0) {
            return true;
        }

        return await showSecretWarning(findings);

    } catch (error) {
    console.error("PasteDB scanner error:", error);
    console.error("Error name:", error?.name);
    console.error("Error message:", error?.message);
    console.error("Error stack:", error?.stack);

    alert(
        `Scanner error: ${error?.name || "Unknown"}\n` +
        `${error?.message || String(error)}`
    );

    return false;
}
}
