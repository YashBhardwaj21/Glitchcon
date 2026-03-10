param(
    [switch]$Verbose,
    [int]$Level = 5
)

$BASE = "http://localhost:8001"
$API_KEY = "1.secret123"
$PASS = 0; $FAIL = 0; $ERR = 0

function Test-Message($label, $msg, $expectedDecision, $expectedCategory, $level, $userId = $null) {
    if ($level -gt $Level) { return }
    $uid = if ($userId) { $userId } else { "tv3_$(Get-Random)" }
    $body = @{ message = $msg; profile_id = "default_test_profile"; user_id = $uid } | ConvertTo-Json -Compress
    try {
        $r = Invoke-RestMethod -Uri "$BASE/v1/moderate/" -Method POST `
            -Headers @{"X-API-Key" = $API_KEY } -ContentType "application/json" -Body $body
        $ok = ($r.decision -eq $expectedDecision) 
        if ($ok) { $script:PASS++ } else { $script:FAIL++ }
        $status = if ($ok) { "PASS" } else { "FAIL" }
        Write-Host "$status  [L$level] $label"
        if (-not $ok -or $Verbose) {
            Write-Host "         Expected : [$expectedDecision] [$expectedCategory]"
            Write-Host "         Got      : [$($r.decision)] [$($r.category)] stage:$($r.stage_triggered) conf:$($r.confidence)"
            if ($r.violated_rule) { Write-Host "         Rule     : $($r.violated_rule)" }
            if ($r.feedback_message) { Write-Host "         Feedback : $($r.feedback_message)" }
        }
        Write-Host ""
    }
    catch {
        $script:ERR++
        Write-Host "ERROR  [L$level] $label"
        Write-Host "         $($_.Exception.Message)"
        Write-Host ""
    }
}

Write-Host "=================================================================="
Write-Host "  MODERATION PIPELINE - TEST SUITE v3 (Simplified / Debugging)"
Write-Host "  Endpoint : $BASE"
Write-Host "  Max Level: $Level"
Write-Host "=================================================================="
Write-Host ""

# ─────────────────────────────────────────────────────────────────────────────
Write-Host "-- LEVEL 1 - Clean messages (must all ALLOW) -------------------"
Write-Host ""
# ─────────────────────────────────────────────────────────────────────────────

Test-Message "L1 - Simple greeting"            "Hello everyone good morning"                                    "ALLOW" "NONE" 1
Test-Message "L1 - Programming question"       "How do I reverse a string in Java"                              "ALLOW" "NONE" 1
Test-Message "L1 - Sports discussion"          "India played very well in the last cricket match"               "ALLOW" "NONE" 1
Test-Message "L1 - Technical help"             "Can someone explain binary search to me"                        "ALLOW" "NONE" 1
Test-Message "L1 - Study discussion"           "I have my exam tomorrow wish me luck"                           "ALLOW" "NONE" 1
Test-Message "L1 - Hinglish casual"            "bhai aaj coding practice karni hai kaafi backlog ho gaya"      "ALLOW" "NONE" 1
Test-Message "L1 - Project discussion"         "Our team finished the machine learning project today"           "ALLOW" "NONE" 1
Test-Message "L1 - Food discussion"            "What did you all eat for lunch today"                           "ALLOW" "NONE" 1
Test-Message "L1 - Technology talk"            "Python is a very useful language for machine learning"          "ALLOW" "NONE" 1
Test-Message "L1 - Friendly chat"              "Nice work on the project it looks great"                        "ALLOW" "NONE" 1

# ─────────────────────────────────────────────────────────────────────────────
Write-Host "-- LEVEL 2 - Clear violations (deterministic stage 1) ----------"
Write-Host ""
# ─────────────────────────────────────────────────────────────────────────────

Test-Message "L2 - Phone number"           "call me at 9876543210"                             "BLOCK" "PII" 2
Test-Message "L2 - Aadhaar simple"         "my aadhaar number is 123456789012"                 "BLOCK" "PII" 2
Test-Message "L2 - Credit card"            "use card 4111111111111111 to pay"                  "BLOCK" "PII" 2

Test-Message "L2 - Profanity simple"       "this code is shit"                                 "BLOCK" "PROFANITY" 2
Test-Message "L2 - Profanity direct"       "you are a fucking idiot"                           "BLOCK" "PROFANITY" 2
Test-Message "L2 - Hindi profanity"        "tu ek chutiya hai"                                 "BLOCK" "PROFANITY" 2

Test-Message "L2 - Hate speech simple"     "those people are animals"                          "BLOCK" "HATE_SPEECH" 2
Test-Message "L2 - Homophobic slur"        "all faggots should be banned"                      "BLOCK" "HATE_SPEECH" 2

# ─────────────────────────────────────────────────────────────────────────────
Write-Host "-- LEVEL 3 - Semantic violations (classifier / FAISS) ----------"
Write-Host ""
# ─────────────────────────────────────────────────────────────────────────────

Test-Message "L3 - Direct threat"            "I will come to your house and hurt you"          "BLOCK" "THREAT" 3
Test-Message "L3 - Indirect threat"          "You better watch your back"                      "BLOCK" "THREAT" 3
Test-Message "L3 - Hinglish threat"          "kal mil tujhe dekh lunga"                        "BLOCK" "THREAT" 3

Test-Message "L3 - Coded communal hate"      "These people always cause trouble in our area"    "BLOCK" "HATE_SPEECH" 3
Test-Message "L3 - Sexism claim"             "Women cannot handle senior engineering pressure"  "BLOCK" "HATE_SPEECH" 3
Test-Message "L3 - Dehumanisation"           "They behave like animals no matter what"          "BLOCK" "HATE_SPEECH" 3

Test-Message "L3 - Scam simple"               "Send 5000 now and get 50000 next week guaranteed" "BLOCK" "SCAM" 3
Test-Message "L3 - Phishing support"          "I am from support share your OTP to verify account" "BLOCK" "SCAM" 3

Test-Message "L3 - Self harm hint"           "I just want to sleep and never wake up"          "BLOCK" "SELF_HARM" 3
Test-Message "L3 - Self harm planning"        "I have been planning this for months and I am ready" "BLOCK" "SELF_HARM" 3

# ─────────────────────────────────────────────────────────────────────────────
Write-Host "-- LEVEL 4 - Adversarial / normalization checks ----------------"
Write-Host ""
# ─────────────────────────────────────────────────────────────────────────────

Test-Message "L4 - Leet bypass"               "n1993r you dont belong here"                         "BLOCK" "HATE_SPEECH" 4
Test-Message "L4 - Dotted slur"               "you are a f.u.c.k.i.n.g idiot"                       "BLOCK" "PROFANITY" 4
Test-Message "L4 - Asterisk bypass"           "what an absolute b*tch move that was uncalled for"   "BLOCK" "PROFANITY" 4
Test-Message "L4 - Zero width / spaced"        "you are a bas tard piece of sh it get out"           "BLOCK" "PROFANITY" 4
Test-Message "L4 - Mixed language simple"      "tu ek chutiya hai bhai stop this"                    "BLOCK" "PROFANITY" 4

Test-Message "L4 - Scam FOMO"                  "Only 2 spots left join now guaranteed returns"       "BLOCK" "SCAM" 4
Test-Message "L4 - Threat rhetorical"          "How would you feel if someone showed up at your house?" "BLOCK" "THREAT" 4

# ─────────────────────────────────────────────────────────────────────────────
Write-Host "-- LEVEL 5 - Easier hard-edge / false-positive traps -----------"
Write-Host ""
# ─────────────────────────────────────────────────────────────────────────────

Test-Message "L5 - Fiction threat explicit"     "In my novel the villain threatens to destroy the city" "ALLOW" "NONE" 5
Test-Message "L5 - Quoting scammer to warn"      "This DM asked me to invest 5k get 50k but it's a scam" "ALLOW" "NONE" 5
Test-Message "L5 - Research on self harm"        "I am analysing posts about suicide for my thesis"     "ALLOW" "NONE" 5
Test-Message "L5 - News report on hate crime"    "Report: Several people arrested for communal hate speech" "ALLOW" "NONE" 5
Test-Message "L5 - Self harm prevention advice"  "If someone is suicidal call local mental-health support" "ALLOW" "NONE" 5
Test-Message "L5 - Academic sexism discussion"    "We must study gender bias in hiring and its causes"     "ALLOW" "NONE" 5
Test-Message "L5 - Flood 1"  "has anyone solved this leetcode problem"  "ALLOW" "NONE" 5 "tv3_spam_user_fixed"
Test-Message "L5 - Flood 2"  "has anyone solved this leetcode problem"  "ALLOW" "NONE" 5 "tv3_spam_user_fixed"
Test-Message "L5 - Flood 3"  "has anyone solved this leetcode problem"  "ALLOW" "NONE" 5 "tv3_spam_user_fixed"
Test-Message "L5 - Flood 4"  "has anyone solved this leetcode problem"  "ALLOW" "NONE" 5 "tv3_spam_user_fixed"
Test-Message "L5 - Flood 5"  "has anyone solved this leetcode problem"  "ALLOW" "NONE" 5 "tv3_spam_user_fixed"
Test-Message "L5 - Flood 6 must block" "has anyone solved this leetcode problem" "BLOCK" "SPAM" 5 "tv3_spam_user_fixed"

# ─────────────────────────────────────────────────────────────────────────────
$TOTAL = $PASS + $FAIL + $ERR
Write-Host "=================================================================="
Write-Host "  RESULTS - TEST SUITE v3 (Simplified)"
Write-Host "  Total : $TOTAL"
Write-Host "  Pass  : $PASS"
Write-Host "  Fail  : $FAIL"
Write-Host "  Error : $ERR"
Write-Host "  Score : $([math]::Round(100 * $PASS / [math]::Max($TOTAL,1), 1))%"
Write-Host "=================================================================="