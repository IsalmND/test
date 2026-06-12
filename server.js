import express from "express";
import cors from "cors";
import axios from "axios";
import * as cheerio from "cheerio";
import puppeteerReal from "puppeteer";
import Database from "better-sqlite3";
import { GoogleGenAI } from "@google/genai";
import fs from "fs";
import path from "path";
import dotenv from "dotenv";

// تفعيل إعدادات البيئة لملف .env
dotenv.config();

const app = express();
app.use(cors());
app.use(express.json({ limit: '50mb' }));

// ==========================================
// 🔑 1. نظام مصفوفة المفاتيح الآمن عبر البيئة
// ==========================================
const API_KEYS_POOL = [
    process.env.GEMINI_API_KEY_1,
    process.env.GEMINI_API_KEY_2,
    process.env.GEMINI_API_KEY_3,
    process.env.GEMINI_API_KEY_4
].filter(Boolean); // تصفية مصفوفة المفاتيح من القيم الفارغة

if (API_KEYS_POOL.length === 0) {
    API_KEYS_POOL.push("PLACEHOLDER_KEY_SETUP_ENV_FILE");
}

let currentKeyIndex = 0;

function getActiveAIInstance() {
    const currentKey = API_KEYS_POOL[currentKeyIndex];
    if (!currentKey || currentKey.trim() === "" || currentKey.includes("PLACEHOLDER")) {
        return null;
    }
    return new GoogleGenAI({ apiKey: currentKey });
}

function rotateToNextKey() {
    if (API_KEYS_POOL.length <= 1) return false;
    currentKeyIndex = (currentKeyIndex + 1) % API_KEYS_POOL.length;
    console.log(`🔄 [نظام التدوير]: تم الانتقال التلقائي للمفتاح رقم [${currentKeyIndex + 1}]`);
    return true;
}

// ==========================================
// 📂 2. تهيئة المجلدات وقاعدة البيانات
// ==========================================
const db = new Database('scanner_intelligence.db');
db.exec(`
    CREATE TABLE IF NOT EXISTS scans ( 
        id INTEGER PRIMARY KEY AUTOINCREMENT, 
        url TEXT, 
        risk TEXT, 
        score INTEGER, 
        issues_json TEXT, 
        scanned_at TEXT 
    ); 
    CREATE TABLE IF NOT EXISTS stats (key TEXT PRIMARY KEY, value INTEGER);
`);
try {
    db.prepare("INSERT OR IGNORE INTO stats (key, value) VALUES ('scans_count', 0)").run();
    db.prepare("INSERT OR IGNORE INTO stats (key, value) VALUES ('total_xp', 0)").run();
} catch(e) {}

const SCRIPTS_DIR = path.join(process.cwd(), "scanned_scripts");
const HISTORY_DIR = path.join(process.cwd(), "scans_history");
[SCRIPTS_DIR, HISTORY_DIR].forEach(dir => {
    if (!fs.existsSync(dir)) {
        fs.mkdirSync(dir, { recursive: true });
    }
});

function getStats() {
    const scans = db.prepare("SELECT value FROM stats WHERE key = 'scans_count'").get()?.value || 0;
    const xp = db.prepare("SELECT value FROM stats WHERE key = 'total_xp'").get()?.value || 0;
    return { scans, xp };
}

function updateStats(newScore) {
    db.prepare("UPDATE stats SET value = value + 1 WHERE key = 'scans_count'").run();
    db.prepare("UPDATE stats SET value = value + ? WHERE key = 'total_xp'").run(newScore);
}

function saveScriptToFile(siteUrl, scriptName, content) {
    try {
        const domain = new URL(siteUrl).hostname.replace(/[^a-zA-Z0-9.-_]/g, "_");
        let cleanName = path.basename(scriptName.split('?')[0]);
        if (!cleanName || cleanName === "/" || cleanName.trim() === "") {
            cleanName = `inline_${Math.floor(Math.random() * 10000)}.js`;
        }
        const sanitizeName = cleanName.replace(/[^a-zA-Z0-9.-_]/g, "_");
        const fileName = `${domain}_[${sanitizeName}]_${Date.now()}.js`;
        const filePath = path.join(SCRIPTS_DIR, fileName);
        fs.writeFileSync(filePath, content, "utf8");
        return fileName;
    } catch (e) {
        return "فشل_أرشفة_الملف";
    }
}

function saveFullSessionArchive(url, reportData) {
    try {
        const domain = new URL(url).hostname.replace(/[^a-zA-Z0-9]/g, "_");
        const sessionFileName = `FullSession_${domain}_${Date.now()}.json`;
        const sessionFilePath = path.join(HISTORY_DIR, sessionFileName);
        fs.writeFileSync(sessionFilePath, JSON.stringify(reportData, null, 2), "utf8");
        return sessionFilePath;
    } catch (e) {
        return null;
    }
}

// ========================================================
// 📦 3. محرك فحص المكتبات المحدث (Multi-Source Hub: OSV & NVD)
// ========================================================
async function checkDependencyVulnerabilities(scriptContent, pushLog) {
    // 🔍 الـ Regex المحدث لتجنب قراءة التواريخ (مثل 2005) والتركيز على الإصدارات الحقيقية
    const match = scriptContent.match(/(jquery|lodash|bootstrap|vue|react)(?:\.js)?[\s@/_-]v?(\d+\.\d+(?:\.\d+)?)/i);
    
    if (match) {
        const libName = match[1].toLowerCase();
        const libVersion = match[2];
        pushLog(`📦 تم رصد مكتبة مستخدمة: [${libName} v${libVersion}] - جاري الفحص المزدوج (OSV & NVD)...`);
        
        let foundVulnerabilities = [];
        const promises = [];

        // المصدر الأول: الاستعلام من قاعدة بيانات OSV (جوجل)
        promises.push(
            axios.post("https://api.osv.dev/v1/query", {
                version: libVersion,
                package: { name: libName, ecosystem: "npm" }
            }, { timeout: 4000 })
            .then(res => ({ source: "OSV", data: res.data }))
            .catch(err => {
                pushLog(`⚠️ فشل الاستعلام من OSV للمكتبة [${libName}]: ${err.message}`);
                return null;
            })
        );

        // المصدر الثاني: الاستعلام من قاعدة البيانات الوطنية الأمريكية للثغرات (NVD - NIST)
        const nvdUrl = `https://services.nvd.nist.gov/rest/json/cves/2.0?keywordSearch=${libName} ${libVersion}`;
        promises.push(
            axios.get(nvdUrl, { timeout: 5000 })
            .then(res => ({ source: "NVD", data: res.data }))
            .catch(err => {
                pushLog(`⚠️ فشل الاستعلام من NVD للمكتبة [${libName}]: ${err.message}`);
                return null;
            })
        );

        // تنفيذ طلبات الـ APIs بالتوازي لضمان أعلى سرعة للفحص
        const results = await Promise.all(promises);

        for (const result of results) {
            if (!result) continue;

            // تجميع نتائج ثغرات OSV
            if (result.source === "OSV" && result.data && result.data.vulns) {
                pushLog(`🚨 [OSV]: تم تأكيد ثغرة عامة مسجلة في مكتبة [${libName}]`);
                result.data.vulns.forEach(v => {
                    foundVulnerabilities.push({
                        issue: `Known Vulnerability in ${libName} (${v.id}) [OSV]`,
                        severity: "HIGH",
                        reason: `المكتبة المستخدمة في الموقع تحتوي على ثغرة برمجية عامة مصنفة بـ OSV: ${v.summary || 'تتطلب التحديث فوراً.'}`,
                        location: `Dependency Tracker (OSV API)`,
                        snippet: `Library: ${libName} | Version: ${libVersion}`,
                        poc_method: "OSV Open Source Vulnerabilities Database API"
                    });
                });
            }

            // تجميع نتائج ثغرات NVD (CVEs)
            if (result.source === "NVD" && result.data && result.data.vulnerabilities) {
                const cves = result.data.vulnerabilities;
                if (cves.length > 0) {
                    pushLog(`🚨 [NVD]: تم رصد عدد (${cves.length}) ثغرة مسجلة في مؤشرات NVD للمكتبة [${libName}]`);
                    cves.forEach(v => {
                        const cveId = v.cve.id;
                        const description = v.cve.descriptions.find(d => d.lang === 'en')?.value || v.cve.descriptions[0]?.value || "";
                        const severity = v.cve.metrics.cvssMetricV31?.[0]?.cvssData?.baseSeverity || "HIGH";
                        
                        foundVulnerabilities.push({
                            issue: `Global CVE Vulnerability ${cveId} in ${libName} [NVD]`,
                            severity: severity.toUpperCase(),
                            reason: `ثغرة أمنية عالمية مسجلة في سجلات NIST: ${description.substring(0, 180)}...`,
                            location: `Dependency Tracker (NVD API)`,
                            snippet: `Library: ${libName} | Version: ${libVersion}`,
                            poc_method: "NIST National Vulnerability Database API Search"
                        });
                    });
                }
            }
        }
        return foundVulnerabilities;
    }
    return [];
}

// ==========================================
// 🤖 4. محرك الذكاء الاصطناعي وتجهيز الحزم
// ==========================================
let lastRawAIResponse = "لا يوجد رد خام بعد، قم بتشغيل فحص أولاً.";

function minifyJSForAI(code) {
    if (!code) return "";
    return code
        .replace(/\/\*[\s\S]*?\*\/|\/\/.*/g, '')
        .replace(/\n\s*\n/g, '\n')
        .replace(/\s+/g, ' ')
        .trim();
}

function obfuscatePayload(payload) {
    let smart = payload.replace(/ /g, "/**/");
    smart = smart.replace(/OR/gi, "oR").replace(/UNION/gi, "UnIoN").replace(/SELECT/gi, "SeLeCt");
    return smart;
}

async function askAIToAnalyzeBundleWithRetry(megaBundleText, attempts = 0) {
    const aiInstance = getActiveAIInstance();
    if (!aiInstance) {
        lastRawAIResponse = { "error": "لا يوجد مفتاح API نشق، تأكد من ملف .env" };
        return { error: true, data: [] };
    }

    if (!megaBundleText || megaBundleText.trim().length < 30) {
        return { error: false, data: [] };
    }

    if (attempts >= API_KEYS_POOL.length) {
        lastRawAIResponse = { "error": "جميع المفاتيح مستهلكة أو غير صالحة" };
        return { error: true, status: "ALL_EXHAUSTED", data: [] };
    }

    try {
        const cleanBundle = minifyJSForAI(megaBundleText);
        const maxChars = 250000;
        const finalBundle = cleanBundle.length > maxChars 
            ? cleanBundle.substring(0, maxChars) + "\n... [تم قص باقي الكود]" 
            : cleanBundle;

        const prompt = `
You are an elite cyber security expert. Analyze this JavaScript bundle for:
1. Hardcoded secrets (API keys, tokens, passwords)
2. DOM XSS sinks (innerHTML, document.write, eval)
3. Prototype Pollution or insecure postMessage handlers
4. Backdoors or malicious fetch exfiltrations

Return ONLY a valid JSON array. If secure, return [].
Format: [{"issue": "Title", "severity": "HIGH|MEDIUM|LOW", "reason": "Arabic technical explanation", "location": "filename", "snippet": "max 120 chars"}]

Bundle Code:
${finalBundle}
`;
        const response = await aiInstance.models.generateContent({
            model: 'gemini-2.0-flash',
            contents: prompt,
        });

        let jsonText = response.text.trim();
        lastRawAIResponse = jsonText;

        if (jsonText.startsWith("```json")) {
            jsonText = jsonText.replace(/^```json\s*/i, '').replace(/```\s*$/i, '').trim();
        } else if (jsonText.includes("```")) {
            jsonText = jsonText.replace(/^```\s*/i, '').replace(/```\s*$/i, '').trim();
        }

        return { error: false, data: JSON.parse(jsonText.trim()) };

    } catch (error) {
        console.warn(`⚠️ فشل المفتاح [${currentKeyIndex + 1}]: ${error.message}`);
        const rotated = rotateToNextKey();
        if (rotated) {
            return await askAIToAnalyzeBundleWithRetry(megaBundleText, attempts + 1);
        } else {
            lastRawAIResponse = { "error": "فشل الاتصال", "details": error.message };
            return { error: true, data: [] };
        }
    }
}

// ==========================================
// 🔍 5. Active Fuzzing - SQL Injection Detection
// ==========================================
async function detectSQLi(page, currentPageUrl, pushLog) {
    const sqliPayloads = [
        "' OR '1'='1",
        "admin' --",
        "' UNION SELECT NULL --",
        "1' AND '1'='1"
    ];
    
    const sqliErrorPatterns = [
        /SQL syntax/i,
        /mysql_fetch/i,
        /SQLite/i,
        /syntax error.*SQL/i,
        /database error/i
    ];
    
    let sqliDetected = false;
    let sqliDetails = [];
    
    try {
        const formStructure = await page.evaluate(() => {
            const forms = document.querySelectorAll('form');
            return Array.from(forms).map((f, fIdx) => {
                const inputs = f.querySelectorAll('input[type="text"], input[type="email"], input[type="password"], input:not([type]), textarea');
                return {
                    formIdx: fIdx,
                    action: f.action || '',
                    inputs: Array.from(inputs).map((i, iIdx) => ({
                        inputIdx: iIdx,
                        name: i.name || i.id || 'unknown'
                    }))
                };
            });
        });
        
        for (let fData of formStructure) {
            for (let iData of fData.inputs) {
                for (let payload of sqliPayloads) {
                    try {
                        await page.goto(currentPageUrl, { waitUntil: 'networkidle2', timeout: 10000 }).catch(() => {});
                        
                        const forms = await page.$$('form');
                        if (!forms[fData.formIdx]) continue;
                        
                        const inputs = await forms[fData.formIdx].$$('input[type="text"], input[type="email"], input[type="password"], input:not([type]), textarea');
                        if (!inputs[iData.inputIdx]) continue;
                        
                        const smartPayload = obfuscatePayload(payload);
                        await inputs[iData.inputIdx].click({ clickCount: 3 });
                        
                        const startTime = Date.now();
                        await inputs[iData.inputIdx].type(smartPayload, { delay: 10 });
                        
                        const submitBtn = await forms[fData.formIdx].$('input[type="submit"], button[type="submit"], button');
                        if (submitBtn) {
                            await Promise.all([
                                submitBtn.click(),
                                page.waitForNetworkIdle({ timeout: 4000 }).catch(() => {})
                            ]);
                            
                            const elapsedTime = Date.now() - startTime;
                            const afterContent = await page.content();
                            
                            for (let pattern of sqliErrorPatterns) {
                                if (pattern.test(afterContent)) {
                                    sqliDetected = true;
                                    sqliDetails.push({ field: iData.name, payload: smartPayload, type: 'error_based' });
                                    pushLog(`🔥 [SQLi Error-Based]: تم رصد خطأ محلي في محتوى الصفحة عند فحص الحقل [${iData.name}]`);
                                    break;
                                }
                            }

                            if (elapsedTime > 5000) {
                                sqliDetected = true;
                                sqliDetails.push({ field: iData.name, payload: smartPayload, type: 'potential_time_based' });
                                pushLog(`🔥 [SQLi Time-Based Warning]: تأخر خادم الاستجابة بشكل مريب (${elapsedTime}ms) عند حقن الحقل [${iData.name}]`);
                            }
                        }
                    } catch (e) { }
                }
            }
        }
    } catch (e) {
        pushLog(`⚠️ فشل فحص SQLi العام: ${e.message}`);
    }
    
    return { sqliDetected, sqliDetails };
}

// ==========================================
// 🔍 6. Reflected XSS Detection
// ==========================================
async function detectReflectedXSS(page, currentPageUrl, pushLog) {
    let reflectedXssDetected = false;
    let reflectedDetails = [];
    
    const xssPayloads = [
        "<script>alert('XSS')</script>",
        "<img src=x onerror=alert('XSS')>",
        "'\"><script>alert('XSS')</script>"
    ];

    try {
        const url = new URL(currentPageUrl);
        if (url.searchParams.toString().length > 0) {
            for (let [key] of url.searchParams.entries()) {
                for (let payload of xssPayloads) {
                    const testUrl = new URL(currentPageUrl);
                    testUrl.searchParams.set(key, payload);
                    
                    try {
                        await page.goto(testUrl.href, { waitUntil: 'networkidle2', timeout: 8000 }).catch(() => {});
                        const content = await page.content();
                        if (content.includes(payload)) {
                            reflectedXssDetected = true;
                            reflectedDetails.push({ param: key, payload: payload, type: 'URL_Param' });
                            pushLog(`🔥 [Reflected XSS]: تم انعكاس الحمولة في باراميتر الرابط [${key}]`);
                        }
                    } catch (e) {}
                }
            }
        }

        await page.goto(currentPageUrl, { waitUntil: 'networkidle2', timeout: 10000 }).catch(() => {});
        const inputElements = await page.evaluate(() => {
            const inputs = document.querySelectorAll('form input[type="text"], form input:not([type])');
            return Array.from(inputs).map((i, idx) => ({ idx, name: i.name || i.id || 'search_input' }));
        });

        for (let inputInfo of inputElements) {
            for (let payload of xssPayloads) {
                try {
                    await page.goto(currentPageUrl, { waitUntil: 'networkidle2', timeout: 10000 }).catch(() => {});
                    const forms = await page.$$('form');
                    
                    let targetInput = null;
                    let targetForm = null;
                    
                    for (let f of forms) {
                        const inputs = await f.$$('input[type="text"], input:not([type])');
                        if (inputs[inputInfo.idx]) {
                            targetInput = inputs[inputInfo.idx];
                            targetForm = f;
                            break;
                        }
                    }

                    if (targetInput && targetForm) {
                        await targetInput.click({ clickCount: 3 });
                        await targetInput.type(payload);
                        
                        const submitBtn = await targetForm.$('input[type="submit"], button[type="submit"], button');
                        if (submitBtn) {
                            await Promise.all([
                                submitBtn.click(),
                                page.waitForNetworkIdle({ timeout: 4000 }).catch(() => {})
                            ]);
                            
                            const resContent = await page.content();
                            if (resContent.includes(payload)) {
                                reflectedXssDetected = true;
                                reflectedDetails.push({ param: inputInfo.name, payload: payload, type: 'Form_Input' });
                                pushLog(`🔥 [Reflected XSS]: تم انعكاس الحمولة عبر نموذج الإدخال في حقل [${inputInfo.name}]`);
                            }
                        }
                    }
                } catch (e) {}
            }
        }
    } catch (e) {
        pushLog(`⚠️ فشل فحص Reflected XSS: ${e.message}`);
    }
    
    return { reflectedXssDetected, reflectedDetails };
}

// ==========================================
// 🔍 7. Session Fixation Detection
// ==========================================
async function detectSessionFixation(page, currentPageUrl, pushLog) {
    let sessionFixationDetected = false;
    let sessionDetails = {};
    
    try {
        const cookiesBefore = await page.cookies();
        const sessionCookieBefore = cookiesBefore.find(c => 
            c.name.toLowerCase().includes('session') || 
            c.name.toLowerCase().includes('jsessionid') ||
            c.name.toLowerCase().includes('phpsessid') ||
            c.name.toLowerCase().includes('sid')
        );
        
        if (sessionCookieBefore) {
            sessionDetails.before = sessionCookieBefore.value;
            sessionDetails.cookieName = sessionCookieBefore.name;
            
            const loginForm = await page.$('form[action*="login"], form[action*="auth"], form[id*="login"], form[class*="login"]');
            if (loginForm) {
                const usernameInput = await loginForm.$('input[name*="user"], input[name*="email"], input[type="text"]');
                const passwordInput = await loginForm.$('input[name*="pass"], input[type="password"]');
                
                if (usernameInput && passwordInput) {
                    await usernameInput.type('test');
                    await passwordInput.type('test');
                    
                    const submitBtn = await loginForm.$('input[type="submit"], button[type="submit"], button');
                    if (submitBtn) {
                        await submitBtn.click();
                        await page.waitForNavigation({ waitUntil: 'networkidle2', timeout: 5000 }).catch(() => {});
                        
                        const cookiesAfter = await page.cookies();
                        const sessionCookieAfter = cookiesAfter.find(c => 
                            c.name.toLowerCase().includes('session') || 
                            c.name.toLowerCase().includes('jsessionid') ||
                            c.name.toLowerCase().includes('phpsessid') ||
                            c.name.toLowerCase().includes('sid')
                        );
                        
                        if (sessionCookieAfter) {
                            sessionDetails.after = sessionCookieAfter.value;
                            if (sessionCookieBefore.value === sessionCookieAfter.value) {
                                sessionFixationDetected = true;
                                pushLog(`🔥 [Session Fixation]: لم تتغير قيمة Session ID بعد محاولة الدخول`);
                            }
                        }
                    }
                }
            }
        }
    } catch (e) {
        pushLog(`⚠️ فشل فحص Session Fixation: ${e.message}`);
    }
    
    return { sessionFixationDetected, sessionDetails };
}

// ==========================================
// 🔍 8. Unvalidated Redirects Detection
// ==========================================
async function detectUnvalidatedRedirects(page, currentPageUrl, pushLog) {
    const redirectParams = ['redirect', 'url', 'dest', 'destination', 'next', 'return', 'goto', 'target', 'rurl', 'continue'];
    let redirectDetected = false;
    let redirectDetails = [];
    
    try {
        const html = await page.content();
        const $ = cheerio.load(html);
        
        $('a[href]').each((i, el) => {
            const href = $(el).attr('href');
            if (href) {
                for (let param of redirectParams) {
                    if (href.includes(`${param}=`)) {
                        redirectDetails.push({
                            originalLink: href,
                            param: param
                        });
                    }
                }
            }
        });
        
        for (let detail of redirectDetails.slice(0, 3)) { 
            try {
                const testUrl = new URL(detail.originalLink, currentPageUrl);
                testUrl.searchParams.set(detail.param, 'https://evil.com');
                
                const testPage = await page.browser().newPage();
                await testPage.goto(testUrl.href, { waitUntil: 'networkidle2', timeout: 6000 });
                
                const finalUrl = testPage.url();
                if (finalUrl.includes('evil.com')) {
                    redirectDetected = true;
                    pushLog(`🔥 [Unvalidated Redirect]: تم التوجيه للنطاق الخبيث عبر [${detail.param}]`);
                }
                await testPage.close();
            } catch (e) {}
        }
    } catch (e) {
        pushLog(`⚠️ فشل فحص Unvalidated Redirects: ${e.message}`);
    }
    
    return { redirectDetected, redirectDetails };
}

// ==========================================
// ⁹. وظائف الاستخراج القياسي
// ==========================================
function analyzeHTML(html, pageUrl) {
    let issues = [];
    const $ = cheerio.load(html);
    let internalLinks = [];
    
    $('a[href]').each((i, el) => {
        const href = $(el).attr('href');
        if (href && !href.startsWith('#') && !href.startsWith('javascript:')) {
            internalLinks.push(href);
        }
    });

    $('form').each((i, el) => {
        if ($(el).find('input[name*="csrf"], input[name*="token"]').length === 0) {
            issues.push({
                issue: "Missing CSRF Protection",
                severity: "MEDIUM",
                reason: "النموذج لا يحتوي على حقول CSRF Token لمنع تزوير العمليات.",
                location: `Page Form [${new URL(pageUrl).pathname}]`,
                snippet: $(el).toString().substring(0, 100),
                poc_method: "Cheerio DOM Parser"
            });
        }
    });

    return {
        issues,
        internalLinks,
        scriptTags: $('script').map((i, el) => $(el).html()).get(),
        externalScripts: $('script[src]').map((i, el) => $(el).attr('src')).get()
    };
}

// ==========================================
// 🚀 10. نقطة الفحص الرئيسية (Crawl & Scan Core)
// ==========================================
let browser;

app.post("/scan", async (req, res) => {
    let { url, skipAI } = req.body;
    if (!url) return res.status(400).json({ error: "URL مطلوب!" });
    if (!/^https?:\/\//i.test(url)) url = 'http://' + url;
    
    let currentLogs = [];
    function pushLog(msg) {
        currentLogs.push(`[${new Date().toLocaleTimeString()}] ${msg}`);
        console.log(msg);
    }

    pushLog(`⚡ تفعيل محرك الفحص المتقدم v6.0 مع Active Fuzzing و OSV/NVD Multi-Tracker...`);

    let pagesToScan = new Set([url]);
    let scannedPages = new Set();
    let uniqueIssues = new Map();
    let rootUrlObj = new URL(url);
    let megaBundleText = "";

    try {
        browser = await puppeteerReal.launch({
            headless: true,
            args: ['--no-sandbox', '--disable-setuid-sandbox', '--disable-dev-shm-usage', '--ignore-certificate-errors']
        });

        const page = await browser.newPage();
        await page.setUserAgent('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36');

        let dynamicXssDetected = false;
        let dynamicXssDetails = null;

        page.on('dialog', async dialog => {
            if (dialog.type() === 'alert') {
                dynamicXssDetected = true;
                dynamicXssDetails = dialog.message();
                pushLog(`🔥 [DOM XSS Confirmed]: ${dynamicXssDetails}`);
                await dialog.dismiss();
            }
        });

        let pageList = Array.from(pagesToScan);

        for (let i = 0; i < Math.min(pageList.length, 15); i++) {
            let currentPageUrl = pageList[i];
            if (scannedPages.has(currentPageUrl)) continue;
            scannedPages.add(currentPageUrl);

            pushLog(`🔍 فحص المسار الحركي: ${currentPageUrl}`);

            await page.goto(currentPageUrl, { waitUntil: 'networkidle2', timeout: 30000 });
            const html = await page.content();
            const headers = page.headers ? await page.headers() : {};

            if (!headers['x-frame-options'] && !headers['content-security-policy']?.includes('frame-ancestors')) {
                const testPage = await browser.newPage();
                await testPage.setContent(`<html><body><iframe src="${currentPageUrl}"></iframe></body></html>`);
                await new Promise(r => setTimeout(r, 1500));
                if (testPage.frames().length > 1) {
                    uniqueIssues.set("CLICKJACKING", {
                        issue: "Confirmed Clickjacking",
                        severity: "MEDIUM",
                        reason: "تم تأكيد إمكانية تضمين الموقع داخل iframe لعدم وجود ترويسات الحماية المناسبة.",
                        location: "Verified via Taint Frame",
                        snippet: `<iframe src="${url}">`,
                        poc_method: "Puppeteer Emulation"
                    });
                }
                await testPage.close();
            }

            if (!headers['content-security-policy']) {
                uniqueIssues.set("CSP_MISSING", {
                    issue: "Missing CSP",
                    severity: "MEDIUM",
                    reason: "الخادم لا يرسل سياسة CSP لحماية المتصفح من حقن السكريبتات.",
                    location: "HTTP Headers",
                    snippet: "content-security-policy: undefined",
                    poc_method: "Headers Audit"
                });
            }

            let htmlRes = analyzeHTML(html, currentPageUrl);
            htmlRes.issues.forEach(iss => uniqueIssues.set(iss.issue + iss.snippet, iss));

            for (let link of htmlRes.internalLinks) {
                try {
                    let absoluteUrl = new URL(link, currentPageUrl).href;
                    if (new URL(absoluteUrl).hostname === rootUrlObj.hostname && !scannedPages.has(absoluteUrl)) {
                        if (!pageList.includes(absoluteUrl)) {
                            pageList.push(absoluteUrl);
                        }
                    }
                } catch(e) {}
            }

            for (let [idx, srcCode] of htmlRes.scriptTags.entries()) {
                if (srcCode && srcCode.trim().length > 50) {
                    saveScriptToFile(currentPageUrl, `inline_${idx+1}`, srcCode);
                    megaBundleText += `\n=== START FILE: Inline #${idx+1} ===\n${srcCode}\n=== END FILE ===\n`;
                    
                    const depVulns = await checkDependencyVulnerabilities(srcCode, pushLog);
                    depVulns.forEach(v => uniqueIssues.set(v.issue + v.snippet, v));
                }
            }

            for (let srcPath of htmlRes.externalScripts) {
                try {
                    if (!srcPath) continue;
                    let fullJsUrl = new URL(srcPath, currentPageUrl).href;
                    if (fullJsUrl.startsWith('http')) {
                        
                        const jsFetch = await axios.get(fullJsUrl, { 
                            timeout: 5000,
                            maxContentLength: 5 * 1024 * 1024, 
                            maxBodyLength: 5 * 1024 * 1024
                        });

                        saveScriptToFile(currentPageUrl, srcPath, jsFetch.data);
                        megaBundleText += `\n=== START FILE: ${srcPath} ===\n${jsFetch.data}\n=== END FILE ===\n`;
                        
                        const depVulns = await checkDependencyVulnerabilities(jsFetch.data, pushLog);
                        depVulns.forEach(v => uniqueIssues.set(v.issue + v.snippet, v));
                    }
                } catch(e) {
                    pushLog(`⚠️ تم تخطي سحب الملف الخارجي لتجاوز حجم الأمان أو فشل الاتصال.`);
                }
            }

            pushLog(`🔍 Active Fuzzing: فحص SQL Injection الحركي والزمني...`);
            const sqliResult = await detectSQLi(page, currentPageUrl, pushLog);
            if (sqliResult.sqliDetected) {
                uniqueIssues.set("SQL_INJECTION_" + currentPageUrl, {
                    issue: "Confirmed SQL Injection Vulnerability",
                    severity: "HIGH",
                    reason: `تم تأكيد ثغرة حقن قواعد البيانات في حقول الإدخال عبر محاكي الاستجابة.`,
                    location: currentPageUrl,
                    snippet: sqliResult.sqliDetails[0]?.payload || "' OR 1=1 --",
                    poc_method: `Active Fuzzing Sandbox Environment`
                });
            }

            pushLog(`🔍 Active Fuzzing: فحص Reflected XSS...`);
            const reflectedResult = await detectReflectedXSS(page, currentPageUrl, pushLog);
            if (reflectedResult.reflectedXssDetected) {
                uniqueIssues.set("REFLECTED_XSS_" + currentPageUrl, {
                    issue: "Confirmed Reflected XSS",
                    severity: "HIGH",
                    reason: `تم رصد عدم معالجة النصوص المدخلة برمجياً مما يسمح بحقن نصوص برمجية خبيثة في المتصفح.`,
                    location: currentPageUrl,
                    snippet: reflectedResult.reflectedDetails[0]?.param || "Search Input/URL Parameter",
                    poc_method: "Input Context Echo Reflection"
                });
            }

            pushLog(`🔍 Active Fuzzing: فحص Session Fixation...`);
            const sessionResult = await detectSessionFixation(page, currentPageUrl, pushLog);
            if (sessionResult.sessionFixationDetected) {
                uniqueIssues.set("SESSION_FIXATION", {
                    issue: "Session Fixation Vulnerability",
                    severity: "HIGH",
                    reason: `لم تتغير قيمة Session ID (${sessionResult.sessionDetails.cookieName}) بعد عملية المصادقة الحية.`,
                    location: currentPageUrl,
                    snippet: `Cookie: ${sessionResult.sessionDetails.cookieName}`,
                    poc_method: "Session ID Comparison"
                });
            }

            pushLog(`🔍 Active Fuzzing: فحص Unvalidated Redirects...`);
            const redirectResult = await detectUnvalidatedRedirects(page, currentPageUrl, pushLog);
            if (redirectResult.redirectDetected) {
                uniqueIssues.set("UNVALIDATED_REDIRECT", {
                    issue: "Unvalidated Redirects and Forwards",
                    severity: "MEDIUM",
                    reason: `تم اكتشاف روابط تقبل التوجيه المفتوح لنطاقات خارجية غير موثوقة.`,
                    location: currentPageUrl,
                    snippet: redirectResult.redirectDetails[0]?.originalLink || "Redirect Parameter",
                    poc_method: "Redirect Parameter Testing"
                });
            }

            if (dynamicXssDetected) {
                uniqueIssues.set("DYNAMIC_XSS", {
                    issue: "Confirmed DOM XSS via Live Sandbox",
                    severity: "HIGH",
                    reason: "تم تفعيل دالة Alert المنعكسة من خلال حقن ديناميكي داخل بيئة الساندبوكس الحية.",
                    location: currentPageUrl,
                    snippet: dynamicXssDetails,
                    poc_method: "DAST Sandbox Injection"
                });
                dynamicXssDetected = false;
            }
        }

        await browser.close();

        let aiStatusInfo = "SUCCESS";
        if (skipAI) {
            aiStatusInfo = "SKIPPED_BY_USER";
            lastRawAIResponse = { "status": "تم تخطي فحص الذكاء الاصطناعي يدوياً لبناء فحص محلي 100%" };
        } else if (megaBundleText.trim().length > 30) {
            pushLog(`🧠 جاري تحليل حزمة الأكواد المستخرجة بالكامل عبر الذكاء الاصطناعي (Gemini AI)...`);
            let aiResult = await askAIToAnalyzeBundleWithRetry(megaBundleText);
            if (aiResult.status === "ALL_EXHAUSTED") {
                aiStatusInfo = "ALL_EXHAUSTED";
            }
            aiResult.data.forEach(iss => {
                iss.poc_method = "Google Gemini AI Analysis";
                if (!iss.severity) iss.severity = "MEDIUM";
                uniqueIssues.set(iss.issue + iss.snippet, iss);
            });
        }

        let finalIssues = Array.from(uniqueIssues.values());
        let totalScore = 0;
        finalIssues.forEach(issue => {
            if (issue.severity === "HIGH") totalScore += 40;
            else if (issue.severity === "MEDIUM") totalScore += 20;
            else totalScore += 10;
        });

        let risk = "LOW";
        if (finalIssues.some(i => i.severity === "HIGH")) {
            risk = "HIGH";
        } else if (finalIssues.some(i => i.severity === "MEDIUM") || totalScore >= 40) {
            risk = "MEDIUM";
        }

        let scannedAtStr = new Date().toLocaleString();

        db.prepare("INSERT INTO scans (url, risk, score, issues_json, scanned_at) VALUES (?, ?, ?, ?, ?)").run(
            url, risk, totalScore, JSON.stringify(finalIssues), scannedAtStr
        );
        updateStats(totalScore);

        let statsObj = getStats();

        const entireExperienceLog = {
            scan_target_url: url,
            security_risk_level: risk,
            total_vulnerability_score: totalScore,
            scanned_at_timestamp: scannedAtStr,
            engine_live_logs: currentLogs,
            detected_vulnerabilities: finalIssues,
            raw_gemini_ai_json_output: lastRawAIResponse
        };

        saveFullSessionArchive(url, entireExperienceLog);

        res.json({
            report: {
                url,
                risk,
                score: totalScore,
                level: Math.floor(statsObj.xp / 100) + 1,
                scanned_at: scannedAtStr,
                issues: finalIssues
            },
            state: {
                scans: statsObj.scans,
                xp: statsObj.xp,
                logs: currentLogs
            },
            raw_api: lastRawAIResponse,
            keyStatus: {
                totalKeys: API_KEYS_POOL.length,
                activeIndex: currentKeyIndex,
                globalStatus: aiStatusInfo
            }
        });

    } catch (error) {
        if (browser) await browser.close();
        res.status(500).json({
            error: "حدث فشل في محرك الفحص الحركي.",
            details: error.message
        });
    }
});

// ==========================================
// 🎨 11. الواجهة الرسومية
// ==========================================
app.get("/", (req, res) => {
    res.send(`<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
    <meta charset="UTF-8">
    <title>CyberShield AI v6.0 - Active Fuzzing Suite</title>
    <link href="https://fonts.googleapis.com/css2?family=Cairo:wght@400;600;700&display=swap" rel="stylesheet">
    <style>
        :root {
            --bg-main: #040406;
            --bg-card: #0a0a0f;
            --bg-input: #0f0f15;
            --border: #151522;
            --primary: #00ffaa;
            --danger: #ff4a5a;
            --warning: #ffb700;
            --info: #00b7ff;
            --text: #f0f0f5;
            --text-muted: #5e5e7a;
        }
        body {
            margin: 0;
            font-family: 'Cairo', sans-serif;
            background: var(--bg-main);
            color: var(--text);
            display: flex;
            height: 100vh;
            overflow: hidden;
        }
        .panel-left {
            width: 30%;
            background: var(--bg-card);
            border-left: 1px solid var(--border);
            padding: 25px;
            display: flex;
            flex-direction: column;
            justify-content: space-between;
            box-sizing: border-box;
        }
        .panel-right {
            width: 70%;
            padding: 30px;
            overflow-y: auto;
            display: flex;
            flex-direction: column;
            gap: 25px;
            box-sizing: border-box;
        }
        input, button {
            width: 100%;
            box-sizing: border-box;
            padding: 14px;
            margin-top: 10px;
            border-radius: 6px;
            font-weight: bold;
        }
        input {
            background: var(--bg-input);
            border: 1px solid var(--border);
            color: #fff;
            text-align: left;
            direction: ltr;
            font-family: monospace;
        }
        button {
            background: linear-gradient(135deg, var(--primary), #00cc88);
            color: #000;
            border: none;
            cursor: pointer;
            font-size: 15px;
        }
        .btn-secondary {
            background: #161624;
            color: #fff;
            border: 1px solid var(--border);
            margin-top: 8px;
        }
        .skip-ai-container {
            display: flex;
            align-items: center;
            gap: 10px;
            margin-top: 12px;
            background: rgba(255, 183, 0, 0.03);
            padding: 10px;
            border-radius: 6px;
            border: 1px dashed rgba(255, 183, 0, 0.15);
        }
        .skip-ai-container input[type="checkbox"] {
            width: auto;
            margin: 0;
            cursor: pointer;
        }
        .skip-ai-container label {
            font-size: 13px;
            color: #ffb700;
            font-weight: bold;
            cursor: pointer;
            user-select: none;
        }
        .terminal {
            background: #010102;
            border: 1px solid var(--border);
            padding: 12px;
            height: 140px;
            overflow-y: auto;
            font-family: monospace;
            font-size: 11px;
            color: #8e8eaf;
            border-radius: 6px;
            line-height: 1.6;
        }
        .grid-stats {
            display: grid;
            grid-template-columns: repeat(3, 1fr);
            gap: 15px;
        }
        .card-stat {
            background: var(--bg-card);
            border: 1px solid var(--border);
            padding: 15px;
            border-radius: 8px;
        }
        .card-stat .num {
            font-size: 22px;
            font-weight: 700;
            color: #fff;
        }
        .gauge-flex {
            display: flex;
            gap: 20px;
            background: var(--bg-card);
            border: 1px solid var(--border);
            padding: 20px;
            border-radius: 8px;
            align-items: center;
        }
        .circle-score {
            width: 90px;
            height: 90px;
            border-radius: 50%;
            border: 6px solid #161622;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 16px;
            font-weight: 700;
            flex-shrink: 0;
        }
        .card-vuln {
            background: var(--bg-card);
            border: 1px solid var(--border);
            padding: 16px;
            border-radius: 6px;
        }
        .card-vuln.sev-HIGH { border-right: 4px solid var(--danger); }
        .card-vuln.sev-MEDIUM { border-right: 4px solid var(--warning); }
        .card-vuln.sev-LOW { border-right: 4px solid var(--info); }
        .badge-sev {
            font-size: 10px;
            padding: 2px 6px;
            border-radius: 4px;
            font-weight: bold;
        }
        .badge-sev.HIGH { background: rgba(255, 74, 90, 0.15); color: var(--danger); }
        .badge-sev.MEDIUM { background: rgba(255, 183, 0, 0.15); color: var(--warning); }
        .badge-sev.LOW { background: rgba(0, 183, 255, 0.15); color: var(--info); }
        .code-view {
            background: #020204;
            padding: 10px;
            border-radius: 4px;
            display: block;
            margin-top: 8px;
            font-family: monospace;
            color: var(--primary);
            font-size: 12px;
            border: 1px solid rgba(0,255,170,0.05);
            white-space: pre-wrap;
            word-break: break-all;
        }
        .poc-view {
            background: #060b08;
            padding: 10px;
            border-radius: 4px;
            display: block;
            margin-top: 8px;
            font-size: 12px;
            color: #a3ffd6;
            border: 1px dashed rgba(0, 255, 170, 0.15);
            white-space: pre-wrap;
        }
        .api-status-card {
            background: #0e0e16;
            border: 1px solid var(--border);
            padding: 12px;
            border-radius: 6px;
            margin-top: 15px;
        }
        .status-row {
            display: flex;
            justify-content: space-between;
            align-items: center;
            font-size: 12px;
            padding: 4px 0;
        }
        .indicator-badge {
            display: flex;
            align-items: center;
            gap: 6px;
            font-weight: bold;
            font-size: 11px;
            padding: 2px 8px;
            border-radius: 12px;
            background: #161624;
        }
        .dot {
            width: 8px;
            height: 8px;
            border-radius: 50%;
            background: #5e5e7a;
        }
        .dot.active {
            background: var(--primary);
            box-shadow: 0 0 8px var(--primary);
        }
        .dot.error {
            background: var(--danger);
            box-shadow: 0 0 8px var(--danger);
        }
        .modal-overlay {
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: rgba(0,0,0,0.85);
            display: none;
            justify-content: center;
            align-items: center;
            z-index: 1000;
        }
        .modal-content {
            background: #0b0b12;
            width: 65%;
            height: 75%;
            border: 1px solid var(--border);
            border-radius: 12px;
            padding: 25px;
            display: flex;
            flex-direction: column;
            gap: 15px;
        }
        .modal-raw-text {
            background: #020205;
            border: 1px solid var(--border);
            color: #ffb700;
            font-family: monospace;
            font-size: 12px;
            padding: 15px;
            border-radius: 6px;
            flex-grow: 1;
            overflow: auto;
            white-space: pre-wrap;
            text-align: left;
            direction: ltr;
        }
    </style>
</head>
<body>
    <div id="aiModal" class="modal-overlay">
        <div class="modal-content">
            <div style="display: flex; justify-content: space-between; align-items: center;">
                <h3 style="margin: 0; color: #ffb700;">📡 مراقبة استجابة AI</h3>
                <button onclick="closeAIModal()" style="width: auto; padding: 6px 16px; background: var(--danger); color: #fff; margin:0;">إغلاق ✕</button>
            </div>
            <div id="rawAIBox" class="modal-raw-text">بانتظار الفحص...</div>
        </div>
    </div>
    <div style="display: flex; width: 100%; height: 100%;">
        <div class="panel-left">
            <div>
                <h2 style="color: var(--primary); margin:0;">🧠 CyberShield PRO <span style="font-size:11px; background:#161622; padding:3px 8px; border-radius:12px; color:#fff;">v6.0</span></h2>
                <p style="color: var(--text-muted); font-size: 12px; margin-top:6px;">نظام تفتيش هجين مع Active Fuzzing لاكتشاف SQLi, XSS, Session Fixation, Redirects</p>
                <div style="margin-top:12px;">
                    <label style="font-size: 12px; color: var(--text-muted);">الرابط المستهدف</label>
                    <input id="url" type="text" placeholder="localhost:8080">
                    
                    <div class="skip-ai-container">
                        <input type="checkbox" id="skipAICheckbox">
                        <label for="skipAICheckbox">🚫 تعطيل فحص الذكاء الاصطناعي (فحص محلي 100%)</label>
                    </div>

                    <button id="btn" onclick="startForensicScan()">تشغيل الفحص المتقدم</button>
                    <button class="btn-secondary" onclick="openAIModal()">👁️ مراقبة رد AI</button>
                </div>
                <div class="api-status-card">
                    <div class="status-row">
                        <span style="color: #aaa; font-weight: 600;">📡 حالة مفاتيح API:</span>
                        <span id="globalKeyBadge" class="indicator-badge"><span id="globalKeyDot" class="dot active"></span> <span id="globalKeyTxt">مستقر</span></span>
                    </div>
                    <div class="status-row" style="border-top: 1px solid #161624; padding-top: 6px;">
                        <span>المفاتيح المتاحة:</span>
                        <span id="totalKeysTxt" style="color: #fff; font-weight: bold;">4</span>
                    </div>
                    <div class="status-row">
                        <span>المفتاح النشط:</span>
                        <span id="activeKeyIndexTxt" style="color: var(--warning); font-weight: bold;">[1]</span>
                    </div>
                </div>
                <div id="statusBox" style="margin-top:12px; padding:10px; background:var(--bg-input); border:1px dashed var(--border); font-size:12px; color:var(--primary); display:none;">
                   ⚙️ <span id="statusTxt">خامل</span>
                </div>
            </div>
            <div>
                <h4 style="margin-bottom:6px; font-size:12px; color: var(--text-muted);">السجلات المباشرة</h4>
                <div id="logs" class="terminal">بانتظار الفحص...</div>
            </div>
        </div>

        <div class="panel-right">
            <div>
                <h2 style="margin:0;">تقرير الفحص الأمني المتقدم</h2>
                <p style="color: var(--text-muted); font-size:12px; margin:4px 0 0 0;">فحص هجين مع Active Fuzzing لاكتشاف الثغرات الحرجة</p>
            </div>

            <div class="grid-stats">
                <div class="card-stat"><div class="lbl" style="font-size:11px; color:var(--text-muted);">الفحوصات</div><div id="sCount" class="num">0</div></div>
                <div class="card-stat"><div class="lbl" style="font-size:11px; color:var(--text-muted);">المستوى</div><div id="lCount" class="num">1</div></div>
                <div class="card-stat"><div class="lbl" style="font-size:11px; color:var(--text-muted);">النقاط (XP)</div><div id="xCount" class="num">0</div></div>
            </div>

            <div class="gauge-flex">
                <div id="gaugeCircle" class="circle-score">N/A</div>
                <div>
                    <h3 id="gTitle" style="margin:0;">جاهز للفحص</h3>
                    <p id="gDesc" style="color: var(--text-muted); font-size: 12px; margin: 4px 0 0 0;">Active Fuzzing + AI Analysis</p>
                </div>
            </div>

            <div>
                <h3 style="margin-bottom: 12px;">الثغرات المكتشفة (<span id="vCount">0</span>)</h3>
                <div id="vulnsBox" style="display:flex; flex-direction:column; gap:12px;">
                    <p style="color: var(--text-muted); font-size:13px;">بانتظار الرابط المستهدف...</p>
                </div>
            </div>
        </div>
    </div>

    <script>
        let currentRawJsonData = "لا يوجد استجابة بعد.";

        async function startForensicScan() {
            const url = document.getElementById("url").value;
            const skipAI = document.getElementById("skipAICheckbox").checked;
            const btn = document.getElementById("btn");
            const sBox = document.getElementById("statusBox");
            const sTxt = document.getElementById("statusTxt");

            if (!url.trim()) return alert("يرجى كتابة الرابط!");
            btn.disabled = true;
            sBox.style.display = "block";
            sTxt.innerText = "جاري تفعيل Active Fuzzing...";

            try {
                const res = await fetch("/scan", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ url, skipAI })
                });
                sTxt.innerText = "فحص SQLi, XSS, Session, Redirects...";
                const data = await res.json();

                if (data.error) {
                    alert(data.error);
                    sTxt.innerText = "فشلت العملية";
                    btn.disabled = false;
                    return;
                }

                sTxt.innerText = "اكتمل الفحص بنجاح";

                document.getElementById("totalKeysTxt").innerText = data.keyStatus.totalKeys;
                document.getElementById("activeKeyIndexTxt").innerText = "[" + (data.keyStatus.activeIndex + 1) + "]";

                const dot = document.getElementById("globalKeyDot");
                const txt = document.getElementById("globalKeyTxt");
                if (data.keyStatus.globalStatus === "ALL_EXHAUSTED") {
                    dot.className = "dot error";
                    txt.innerText = "مستنفذة!";
                    txt.style.color = "var(--danger)";
                } else if (data.keyStatus.globalStatus === "SKIPPED_BY_USER") {
                    dot.className = "dot";
                    txt.innerText = "معطل يدوياً";
                    txt.style.color = "var(--warning)";
                } else {
                    dot.className = "dot active";
                    txt.innerText = "مستقر";
                    txt.style.color = "var(--primary)";
                }

                document.getElementById("sCount").innerText = data.state.scans;
                document.getElementById("lCount").innerText = data.report.level;
                document.getElementById("xCount").innerText = data.state.xp;
                document.getElementById("vCount").innerText = data.report.issues.length;

                currentRawJsonData = data.raw_api;
                document.getElementById("rawAIBox").innerText = typeof currentRawJsonData === 'object' ? JSON.stringify(currentRawJsonData, null, 2) : currentRawJsonData;

                const gc = document.getElementById("gaugeCircle");
                gc.innerText = data.report.score + " pts";
                let currentRisk = data.report.risk;
                
                if (currentRisk === "HIGH") {
                    gc.style.borderColor = "var(--danger)";
                    document.getElementById("gTitle").innerHTML = "<span style='color:var(--danger)'>مخاطر عالية</span>";
                    document.getElementById("gDesc").innerText = "تم رصد ثغرات حرجة";
                } else if (currentRisk === "MEDIUM") {
                    gc.style.borderColor = "var(--warning)";
                    document.getElementById("gTitle").innerHTML = "<span style='color:var(--warning)'>مخاطر متوسطة</span>";
                    document.getElementById("gDesc").innerText = "ثغرات متوسطة الأثر";
                } else {
                    gc.style.borderColor = "var(--primary)";
                    document.getElementById("gTitle").innerHTML = "<span style='color:var(--primary)'>آمن</span>";
                    document.getElementById("gDesc").innerText = "الأكواد آمنة";
                }

                const box = document.getElementById("vulnsBox");
                if (data.report.issues.length === 0) {
                    box.innerHTML = "<div class='card-vuln'><b>✔ الفحص نظيف</b></div>";
                } else {
                    let cardsHtml = "";
                    for (let i = 0; i < data.report.issues.length; i++) {
                        let iss = data.report.issues[i];
                        cardsHtml += '<div class="card-vuln sev-' + iss.severity + '">' +
                            '<div style="font-weight:bold; font-size:15px; display:flex; justify-content:space-between; align-items: center;">' +
                                '<span>⚠️ ' + escapeHtml(iss.issue) + ' <span class="badge-sev ' + iss.severity + '">' + iss.severity + '</span></span>' +
                                '<span style="font-size:11px; background:rgba(255,255,255,0.04); padding:2px 6px; border-radius:4px;">' + escapeHtml(iss.location) + '</span>' +
                            '</div>' +
                            '<div style="font-size:12px; color:var(--text-muted); margin:6px 0 4px 0;">' + escapeHtml(iss.reason) + '</div>' +
                            '<div style="font-size:11px; font-weight:bold; color:var(--primary); margin-top:10px;">⚙️ آلية التحقق:</div>' +
                            '<div class="poc-view">' + escapeHtml(iss.poc_method) + '</div>' +
                            '<div style="font-size:11px; font-weight:bold; color:#aaa; margin-top:8px;">📊 Snippet:</div>' +
                            '<span class="code-view">' + escapeHtml(iss.snippet) + '</span>' +
                        '</div>';
                    }
                    box.innerHTML = cardsHtml;
                }

                let logsHtml = "";
                for (let i = 0; i < data.state.logs.length; i++) {
                    logsHtml += "<div>" + data.state.logs[i] + "</div>";
                }
                document.getElementById("logs").innerHTML = logsHtml;

            } catch(e) {
                alert("حدث خطأ أثناء الفحص المحلي.");
            } finally {
                btn.disabled = false;
            }
        }

        function openAIModal() {
            document.getElementById("aiModal").style.display = "flex";
            document.getElementById("rawAIBox").innerText = typeof currentRawJsonData === 'object' ? JSON.stringify(currentRawJsonData, null, 2) : currentRawJsonData;
        }

        function closeAIModal() {
            document.getElementById("aiModal").style.display = "none";
        }

        function escapeHtml(str) {
            return String(str).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
        }
    </script>
</body>
</html>`);
});

// ==========================================
// ⚙️ 12. تشغيل النظام
// ==========================================
app.listen(3000, () => {
    console.log("=================================================");
    console.log("🚀 CyberShield v6.0 Active Fuzzing Suite Online!");
    console.log("📁 Scripts: ./scanned_scripts");
    console.log("📂 History: ./scans_history");
    console.log("🌐 Dashboard: http://localhost:3000");
    console.log("=================================================");
});