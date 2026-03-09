# test_categorization.ps1
# Run from service/ directory after uvicorn is running on port 8001
#
# Usage:
#   .\test_categorization.ps1
#   .\test_categorization.ps1 -Verbose    # shows full response JSON
#   .\test_categorization.ps1 -Level 3    # run only up to difficulty level 3

param(
    [switch]$Verbose,
    [int]$Level = 5
)

$BASE = "http://localhost:8001"
$API_KEY = "1.secret123"

$PASS = 0
$FAIL = 0
$ERR = 0

function Test-Message($label, $msg, $expectedDecision, $expectedCategory, $level) {
    if ($level -gt $Level) { return }

    $body = @{
        message    = $msg
        profile_id = "default_test_profile"
        user_id    = "test_cat_$(Get-Random)"
    } | ConvertTo-Json -Compress

    try {
        $r = Invoke-RestMethod -Uri "$BASE/v1/moderate/" -Method POST `
            -Headers @{"X-API-Key" = $API_KEY } `
            -ContentType "application/json" -Body $body

        $decisionOk = $r.decision -eq $expectedDecision
        $categoryOk = $r.category -eq $expectedCategory
        $status = if ($decisionOk -and $categoryOk) { "✅ PASS" } else { "❌ FAIL" }

        if ($decisionOk -and $categoryOk) { $script:PASS++ } else { $script:FAIL++ }

        Write-Host "$status  [L$level] $label"
        if (-not $decisionOk -or -not $categoryOk -or $Verbose) {
            Write-Host "         Expected : [$expectedDecision] [$expectedCategory]"
            Write-Host "         Got      : [$($r.decision)] [$($r.category)] stage:$($r.stage_triggered) conf:$($r.confidence)"
            if ($r.violated_rule) {
                Write-Host "         Rule     : $($r.violated_rule)"
            }
            if ($r.feedback_message) {
                Write-Host "         Feedback : $($r.feedback_message)"
            }
        }
        Write-Host ""
    }
    catch {
        $script:ERR++
        Write-Host "💥 ERROR  [L$level] $label"
        Write-Host "         $($_.Exception.Message)"
        Write-Host ""
    }
}

# ─────────────────────────────────────────────────────────────────────────────
Write-Host "=================================================================="
Write-Host "  MODERATION PIPELINE - CATEGORIZATION TEST SUITE"
Write-Host "  Endpoint : $BASE"
Write-Host "  Max Level: $Level"
Write-Host "=================================================================="
Write-Host ""

# ─────────────────────────────────────────────────────────────────────────────
Write-Host "-- LEVEL 1 - Clean messages (all should ALLOW / NONE) ----------"
Write-Host ""
# ─────────────────────────────────────────────────────────────────────────────
Test-Message "Basic greeting"               "Hey what time does the meeting start?"                          "ALLOW" "NONE" 1
Test-Message "Technical question EN"        "Can you help me with Python list comprehensions?"               "ALLOW" "NONE" 1
Test-Message "Technical question HI"        "mujhe Python seekhni hai, kahan se shuru karun?"               "ALLOW" "NONE" 1
Test-Message "Religious expression EN"      "God bless everyone reading this"                               "ALLOW" "NONE" 1
Test-Message "Religious expression HI"      "Allah sabko khush rakhe aur salamat rakhe"                     "ALLOW" "NONE" 1
Test-Message "Identity mention positive"    "The trans women reading this tweet right now is beautiful"     "ALLOW" "NONE" 1
Test-Message "Compliment"                   "Complicated black haired women are the best"                   "ALLOW" "NONE" 1
Test-Message "Sports fan"                   "Hero Rohit Sharma love from Pakistan"                          "ALLOW" "NONE" 1
Test-Message "Neutral news"                 "Officials have waived work permit requirements for non-citizens" "ALLOW" "NONE" 1
Test-Message "LGBTQ+ supportive"            "Nice! As a bi couple, we thoroughly enjoy bi dad friends"      "ALLOW" "NONE" 1
Test-Message "Sensitive topic neutral"      "Sexual harassment is a serious issue we must discuss openly"   "ALLOW" "NONE" 1
Test-Message "Competitive game"             "I want to destroy you in this chess game bro"                  "ALLOW" "NONE" 1
Test-Message "Casual Hinglish"              "bhai aaj ka lecture bahut boring tha yaar"                     "ALLOW" "NONE" 1
Test-Message "Hindi news"                   "aaj ka mausam bahut accha hai, bahar jaao"                     "ALLOW" "NONE" 1

# ─────────────────────────────────────────────────────────────────────────────
Write-Host "-- LEVEL 2 - Obvious violations (Stage 1 should catch) ---------"
Write-Host ""
# ─────────────────────────────────────────────────────────────────────────────
Test-Message "PII - Indian mobile"          "Call me at 9876543210 for the deal"                            "BLOCK" "PII" 2
Test-Message "PII - Aadhaar"                "My Aadhaar is 9876 5432 1098, please verify"                   "BLOCK" "PII" 2
Test-Message "PII - PAN card"               "My PAN is ABCDE1234F, use it for KYC"                         "BLOCK" "PII" 2
Test-Message "PII - Email"                  "Send me your details at test@gmail.com right now"              "BLOCK" "PII" 2
Test-Message "PII - UPI"                    "Send money to yash@okicici for the product"                    "BLOCK" "PII" 2
Test-Message "Profanity direct EN"          "you are a fucking piece of shit"                               "BLOCK" "PROFANITY" 2
Test-Message "Profanity leet speak"         "you are such a @sshole"                                        "BLOCK" "PROFANITY" 2
Test-Message "Hindi slur direct"            "madarchod sala nikal yahan se"                                 "BLOCK" "PROFANITY" 2
Test-Message "Hindi Devanagari slur"        "मादरचोद भाग यहाँ से तू"                                        "BLOCK" "PROFANITY" 2
Test-Message "Racial slur direct"           "You stupid nigger get out of here"                             "BLOCK" "HATE_SPEECH" 2
Test-Message "Crypto scam direct"           "Buy Bitcoin now guaranteed 10x returns DM me"                  "BLOCK" "SCAM" 2
Test-Message "Self harm direct"             "what dose of pills makes you not wake up"                      "BLOCK" "SELF_HARM" 2

# ─────────────────────────────────────────────────────────────────────────────
Write-Host "-- LEVEL 3 - Indirect violations (LLM should catch) -----------"
Write-Host ""
# ─────────────────────────────────────────────────────────────────────────────
Test-Message "Threat indirect"              "I know where you live. Be careful walking home tonight."       "BLOCK" "THREAT" 3
Test-Message "Dehumanisation"               "These people are like cockroaches, they breed everywhere"      "BLOCK" "HATE_SPEECH" 3
Test-Message "Gender discrimination"        "Women belong in the kitchen, not in tech. Fire all female engineers." "BLOCK" "HATE_SPEECH" 3
Test-Message "Doxxing attempt"              "His address is 42 MG Road Mumbai. Go pay him a visit."         "BLOCK" "THREAT" 3
Test-Message "Phishing OTP"                 "Send me your bank OTP on WhatsApp for verification"            "BLOCK" "PII" 3
Test-Message "Fake investment scheme"       "I know a way to make 10x returns on crypto, DM me privately"  "BLOCK" "SCAM" 3
Test-Message "Self harm indirect"           "a gentle way to fall asleep and not wake up again"             "BLOCK" "SELF_HARM" 3
Test-Message "Casteism India"               "bloody bhangi go back to cleaning drains"                      "BLOCK" "HATE_SPEECH" 3
Test-Message "Communal hate India"          "all muslims should be thrown out of this country"              "BLOCK" "HATE_SPEECH" 3
Test-Message "Hindi indirect threat"        "tere ghar ka pata hai mujhe, sambhal ke rehna"                 "BLOCK" "THREAT" 3
Test-Message "Hinglish threat"              "is bande ko maar do sala harami hai"                           "BLOCK" "THREAT" 3
Test-Message "Hinglish scam"                "crypto mein paisa laga guaranteed double hoga bhai"            "BLOCK" "SCAM" 3

# ─────────────────────────────────────────────────────────────────────────────
Write-Host "-- LEVEL 4 - Bypass attempts (normaliser + LLM should catch) ---"
Write-Host ""
# ─────────────────────────────────────────────────────────────────────────────
Test-Message "Leet speak hate"              "n1gg3r get out of here"                                        "BLOCK" "HATE_SPEECH" 4
Test-Message "Spaced out slur"              "f u c k o f f y o u b a s t a r d"                            "BLOCK" "PROFANITY" 4
Test-Message "Dotted slur"                  "what a f.u.c.k.i.n.g idiot you are"                           "BLOCK" "PROFANITY" 4
Test-Message "Repeated chars slur"          "you fuuuucking moron get out"                                  "BLOCK" "PROFANITY" 4
Test-Message "Mixed script bypass"          "m@d@rch0d nikal yahan se"                                      "BLOCK" "PROFANITY" 4
Test-Message "Scam with emoji"              "💰 guaranteed 10x Bitcoin returns 🚀 DM me now 💰"             "BLOCK" "SCAM" 4
Test-Message "Threat with asterisks"        "I will f*** you up when I find you"                            "BLOCK" "THREAT" 4
Test-Message "Subtle self harm"             "anyone know the maximum safe dose of sleeping pills?"          "BLOCK" "SELF_HARM" 4
Test-Message "Code mixed hate"              "ye saale ch*tiyo ko maar do yaar"                              "BLOCK" "HATE_SPEECH" 4
Test-Message "Polite phrased threat"        "I would strongly advise you to watch your back from now on"    "BLOCK" "THREAT" 4

# ─────────────────────────────────────────────────────────────────────────────
Write-Host "-- LEVEL 5 - Edge cases and tricky scenarios -------------------"
Write-Host ""
# ─────────────────────────────────────────────────────────────────────────────
Test-Message "Fiction violence"             "In my novel, the villain says he will kill the hero"           "ALLOW" "NONE" 5
Test-Message "News report violence"         "Unconfirmed reports of the murder of former bodyguard in Cape Town" "ALLOW" "NONE" 5
Test-Message "Academic hate speech"         "The study found that hate speech increases during elections"   "ALLOW" "NONE" 5
Test-Message "Quoting to report"            "Someone just told me to kill myself, should I report it?"      "ALLOW" "NONE" 5
Test-Message "Medical overdose context"     "The patient accidentally took an overdose of medication"       "ALLOW" "NONE" 5
Test-Message "Sarcastic compliment"         "Oh great, another genius has arrived to save us all"           "ALLOW" "NONE" 5
Test-Message "Profanity in positive context" "This new feature is absolutely f***ing amazing!"              "ALLOW" "NONE" 5
Test-Message "Minority mention neutral"     "The study included 400 participants from minority communities" "ALLOW" "NONE" 5
Test-Message "Political criticism"          "This government policy is completely wrong and harmful"        "ALLOW" "NONE" 5
Test-Message "Competitive trash talk"       "bhai teri team toh seedhi bahar ho jaayegi aaj"               "ALLOW" "NONE" 5
Test-Message "Spam flood 1"                 "hello this is message one"                                     "ALLOW" "NONE" 5
Test-Message "Spam flood 2"                 "hello this is message two"                                     "ALLOW" "NONE" 5
Test-Message "Spam flood 3"                 "hello this is message three"                                   "ALLOW" "NONE" 5
Test-Message "Spam flood 4"                 "hello this is message four"                                    "ALLOW" "NONE" 5
Test-Message "Spam flood 5"                 "hello this is message five"                                    "ALLOW" "NONE" 5
Test-Message "Spam flood 6 - should block" "hello this is message six"                                     "BLOCK" "SPAM" 5

# ─────────────────────────────────────────────────────────────────────────────
$TOTAL = $PASS + $FAIL + $ERR
Write-Host "=================================================================="
Write-Host "  RESULTS"
Write-Host "  Total : $TOTAL"
Write-Host "  Pass  : $PASS ✅"
Write-Host "  Fail  : $FAIL ❌"
Write-Host "  Error : $ERR 💥"
Write-Host "  Score : $([math]::Round(100 * $PASS / [math]::Max($TOTAL,1), 1))%"
Write-Host "=================================================================="