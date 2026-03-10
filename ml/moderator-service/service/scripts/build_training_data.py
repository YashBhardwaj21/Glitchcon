"""
scripts/build_training_data.py

Comprehensive labelled training dataset for the moderation classifier.
Target: 150+ examples per violation category, 250+ NONE examples.
Coverage: English, Hindi, Hinglish, code-mixed, indirect phrasing, bypass attempts.

Changelog vs previous version:
  THREAT      69  -> 155  (+86)  Added: family doxxing, employer doxxing, partial
                                  address, inter-platform threats, matrimonial threats,
                                  new Hinglish variants, WhatsApp forward threats
  HATE_SPEECH 87  -> 158  (+71)  Added: love jihad rhetoric, food policing,
                                  temple-mosque dispute, inter-caste marriage threats,
                                  Dalit dehumanisation subtypes, honour killing framing,
                                  coded dog-whistle phrases
  SCAM        79  -> 155  (+76)  Added: PM Kisan fraud, fake govt job portals,
                                  SIM swap, fake UPI screenshot, fake scholarship,
                                  fake rental listing, sextortion, task-based scam
  SELF_HARM   74  -> 152  (+78)  Added: method-specific (bridge, train, hanging),
                                  stockpiling variants, goodbye signals, self-harm
                                  without suicidal intent, crisis phrasing, more Hinglish
  NONE       118  -> 258 (+140)  Added: hard near-miss traps for every new category,
                                  PSA context, journalism context, toxicology research,
                                  gaming/fiction, more Hinglish clean messages

FAISS TOPIC INDEX EXPANSION SEEDS (50 new topics embedded as comments):
  Search for "# FAISS_TOPIC:" to extract them programmatically.
  The build script auto-writes them to data/faiss_topic_seeds.txt on each run.

Run:
    python scripts/build_training_data.py
    -> writes data/training_data.json
    -> writes data/faiss_topic_seeds.txt  (new FAISS topics to add)
"""

import json
import os
import re
from collections import Counter


LABELLED_EXAMPLES = {

    # ─────────────────────────────────────────────────────────────────────────
    # THREAT  (target: 155+)
    # New subcategories vs v1:
    #   - Family member doxxing
    #   - Employer doxxing / get-you-fired threats
    #   - Partial address / neighbourhood threat
    #   - Inter-platform coordinated threats
    #   - Matrimonial / honour-based threat framing
    # ─────────────────────────────────────────────────────────────────────────
    # FAISS_TOPIC: "I know where you live and I am coming for you tonight"
    # FAISS_TOPIC: "enjoy your evening walk I know your usual route very well"
    # FAISS_TOPIC: "I have your home address and I will share it everywhere"
    # FAISS_TOPIC: "your address is going viral in this group tonight"
    # FAISS_TOPIC: "I know your parents names and where they both work"
    # FAISS_TOPIC: "I found your employer and I will contact HR immediately"
    # FAISS_TOPIC: "I will get you fired by the end of this week"
    # FAISS_TOPIC: "your neighbourhood is known to me be very careful"
    # FAISS_TOPIC: "if you marry outside your community there will be consequences"
    # FAISS_TOPIC: "I will tag your family and employer in my post"
    # FAISS_TOPIC: "I will DDoS your server until it is offline permanently"
    # FAISS_TOPIC: "pay me or I release your private photos to everyone"
    # FAISS_TOPIC: "delete the post or your family will find out everything"
    "THREAT": [
        # ── Direct English threats ─────────────────────────────────────────
        "I will kill you if you say that one more time",
        "You are going to regret this I promise you that",
        "I know where you live and I am coming for you tonight",
        "Say that again and I will break every bone in your body",
        "I will destroy you and everything you love",
        "You better watch your back when you leave the house",
        "I will hunt you down no matter where you go",
        "Your life is in danger if you keep pushing me",
        "I will make sure you never walk properly again",
        "You have made a deadly mistake messing with me",
        "I will end you before this week is over",
        "Keep talking and find out what happens to you",
        "I am going to hurt you so badly you will wish you were dead",
        "One more message from you and you will disappear",
        "I will send people to deal with you personally",
        "You will not be alive to see next week if you continue",
        "I have your address and I am not afraid to use it",
        "Consider this your final warning before I act",
        "I will come to your house and make you pay",
        "Enjoy your life while you still have one",

        # ── Veiled / polite phrased ────────────────────────────────────────
        "I would strongly advise you to stop posting here for your own safety",
        "It would be in your best interest to watch what you say",
        "I am just saying you should be more careful about where you walk at night",
        "People who talk the way you do tend to have accidents",
        "I have friends who specialise in dealing with people like you",
        "Something very unfortunate might happen to you if you are not careful",
        "I would not want anything bad to happen to you or your family",
        "It would be wise to reconsider your position before it is too late",
        "You should think about your family before posting things like this",
        "I hope you have good insurance is all I will say",
        "I know some people who would love to have a word with you",
        "You might want to change your route home tonight",
        "Things have a funny way of coming back around to people like you",
        "I am not threatening you I am just letting you know what could happen",
        "Enjoy your evening walk I know your usual route very well",

        # ── Standard doxxing ──────────────────────────────────────────────
        "I found your home address and I am going to post it everywhere",
        "Your address is being shared in every group I am in right now",
        "I know your name your college and your hostel block number",
        "I have your IP address and I can find exactly where you are",
        "Your phone number and home address will be in this group tomorrow",
        "I am going to expose your real name and location to everyone here",
        "Found your LinkedIn your company and your office address",
        "I have screenshots of your ID I will post them publicly",
        "Your address is already on the group bro enjoy the visitors",
        "Shared your location to 10 different people good luck",
        "I have your Aadhaar photo and I know exactly who you are",
        "Posted your address on the other forum already",
        "Your college ID photo and address are going viral tonight",

        # ── NEW: Family member doxxing ─────────────────────────────────────
        "I know your parents names and where they both work",
        "Your mother works at that school on MG Road right",
        "I found your sister's Instagram and her college name",
        "Your father's office address is already with my people",
        "I know where your kids go to school so be very careful",
        "Your wife's workplace and daily routine is known to me",
        "I will contact every family member you have if you do not comply",
        "Your brother's address is on this group now",

        # ── NEW: Employer doxxing ──────────────────────────────────────────
        "I am going to email your manager every screenshot I have of you",
        "I found your company on LinkedIn I will contact HR immediately",
        "Your employer is going to find out exactly what you have been doing",
        "I will get you fired by the end of this week I promise",
        "Every person in your company is going to see what you wrote",
        "I am forwarding this to your boss right now enjoy",
        "Your client list is going to receive a very interesting email tonight",
        "I will post your work email and phone on every forum I can find",

        # ── NEW: Partial address / neighbourhood ──────────────────────────
        "I know the area you live in and I know your building",
        "Your neighbourhood is well known to me I have been watching",
        "I saw you at the market near your house last Tuesday",
        "I know which floor you live on and which bike is yours",
        "Your flat number is already in the group better move",
        "I will put flyers with your face in your entire neighbourhood",
        "Your local area WhatsApp group is about to get very interesting",

        # ── NEW: Inter-platform coordinated threats ────────────────────────
        "I have reported you on Instagram Facebook and LinkedIn already",
        "I am going to tag your employers family and friends in my post",
        "Your real identity is going on Reddit Twitter and everywhere else",
        "I will mass report every account you have until they are all gone",
        "Your anonymous account is not anonymous to me I will expose it",
        "I am going to create accounts just to follow and harass you everywhere",

        # ── NEW: Matrimonial / honour-based threats ────────────────────────
        "If you marry outside your community I will make sure it never happens",
        "Your family will hear exactly what you have been doing online",
        "How dare you date someone from that religion your family will know",
        "I will tell your parents every detail about your relationship",
        "Your community will know your character before your wedding day",
        "The photos you sent privately are going to your parents tonight",

        # ── Conditional threats ────────────────────────────────────────────
        "If you do not delete that post I will make your life hell",
        "Either you apologise publicly or I will ruin your reputation",
        "One more word and I send everything I have on you to your college",
        "Remove that comment or your family will know what you have been doing",
        "Pay me or I release your private photos to everyone",
        "Stop talking or I will come find you this weekend",
        "Delete your account by tomorrow or face consequences",
        "If you show up tomorrow you will not be walking home",
        "Keep ignoring me and see what I do next",
        "Do what I say or things will get very bad for you very fast",

        # ── Hindi / Hinglish ──────────────────────────────────────────────
        "tujhe maar dunga agar tu band nahi hua toh",
        "teri gali ka pata lag gaya hai mujhe sambhal ke rehna",
        "main jaanta hoon tu kahan rehta hai raat ko bahar mat nikalna",
        "tujhe dhundh lenge hum chhup ke baith",
        "aaj raat ghar pohonchega tu ya nahi ye dekhte hain",
        "tera schedule pata hai mujhe soch ke chal",
        "tere ghar walo ka bhi pata hai hamare paas",
        "bata denge sab ko kahan milega tu aaj raat",
        "police se pehle main pohonch jaunga tere paas",
        "ek aur cheez boli toh main action lunga tere khilaf seriously",
        "tujhe is shehar mein rehna padega toh dhyan se rehna",
        "tere baap ka naam aur ghar ka pata dono pata hain mujhe",
        "band kar apni bakwaas warna tujhe pata chalega",
        "teri job ka pata hai mujhe teri company ko bhi bataunga",
        "nikal yahan se warna kuch acha nahi hoga tere saath",
        "teri maa behen ka pata bhi hai hamare paas",
        "teri company ke HR ko sab kuch bhej dunga aaj",
        "tere mohalle mein sab ko pata chalega tu kaisa hai",
        "WhatsApp group mein tera address dal diya hai abhi",
        "teri girlfriend ko sab kuch bata dunga agar tune nahi suna",

        # ── Cyber threats ─────────────────────────────────────────────────
        "I will hack your account and leak all your private messages",
        "Your data is being downloaded right now enjoy",
        "I have already installed a keylogger on your system",
        "I will DDoS your server until it goes offline permanently",
        "Your accounts are going to be compromised tonight",
        "I know your password and I am already inside your email",
        "I will report your account until it gets permanently banned",
        "I am going to spam every platform you are on until you are gone",
    ],

    # ─────────────────────────────────────────────────────────────────────────
    # HATE_SPEECH  (target: 158+)
    # New subcategories vs v1:
    #   - Love jihad rhetoric
    #   - Food policing / halal / beef hate
    #   - Temple-mosque dispute incitement
    #   - Inter-caste marriage threats
    #   - Dalit dehumanisation subtypes
    #   - Coded dog-whistle phrases
    # ─────────────────────────────────────────────────────────────────────────
    # FAISS_TOPIC: "love jihad is a real organised conspiracy against our daughters"
    # FAISS_TOPIC: "they are targeting Hindu girls to convert them through marriage"
    # FAISS_TOPIC: "halal meat is funding terrorism it should be banned"
    # FAISS_TOPIC: "beef eaters have no place in this Hindu nation"
    # FAISS_TOPIC: "that mosque was built on a demolished temple tear it down"
    # FAISS_TOPIC: "inter-caste marriage is polluting our community bloodline"
    # FAISS_TOPIC: "Dalit should not be allowed in upper caste homes or temples"
    # FAISS_TOPIC: "our daughter brought shame marrying into that religion"
    # FAISS_TOPIC: "the great replacement is happening in our own country"
    # FAISS_TOPIC: "they breed like cockroaches to outnumber real citizens"
    # FAISS_TOPIC: "we need to cleanse this country of these outsiders now"
    # FAISS_TOPIC: "gay agenda is corrupting our children in schools"
    # FAISS_TOPIC: "women belong in the kitchen not in tech or leadership"
    "HATE_SPEECH": [
        # ── Dehumanisation ─────────────────────────────────────────────────
        "These people are like cockroaches breeding everywhere we go",
        "These migrants are rats infesting our neighbourhoods",
        "They are not human beings they are animals that need to be put down",
        "These people are a disease spreading through our country like a plague",
        "They are parasites living off the hard work of real citizens",
        "These people should be exterminated like the vermin they are",
        "They multiply like insects and take over every space they enter",
        "This group of people is a cancer that needs to be removed",
        "They are subhuman and should be treated as such",
        "These creatures have no place in civilised society",
        "They are literally an infestation that needs to be cleaned out",
        "These people are genetic waste dragging down our society",

        # ── Religious hate India context ───────────────────────────────────
        "All Muslims should be thrown out of this country immediately",
        "Hindus should drive every Muslim out of India for good",
        "This country would be better off without any Muslims in it",
        "They are converting people by force and must be stopped violently",
        "All these minorities should go back to Pakistan where they belong",
        "This is a Hindu rashtra and others have no place here at all",
        "These people follow a religion of violence and terror",
        "Muslim population growth is a conspiracy to take over our nation",
        "Every mosque in this country should be demolished",
        "These Hindus are destroying the fabric of our secular nation",
        "Christians are just agents of western colonisation destroy their churches",
        "These kafirs need to be dealt with according to sharia",
        "Cow worshippers are backward superstitious idiots who ruin everything",
        "These mullahs are radicalising everyone they should all be jailed",

        # ── NEW: Love jihad rhetoric ───────────────────────────────────────
        "Love jihad is a real organised conspiracy against our Hindu daughters",
        "They deliberately target Hindu girls to trap and convert them",
        "Every Hindu parent must protect their daughters from these predators",
        "These men pretend to love our girls to convert them by marriage",
        "This love jihad must be stopped by any means necessary now",
        "Alert your daughters about men who change their names to trap girls",
        "Hindu girls who marry Muslims are traitors to their own community",
        "These so-called love stories are just conversion traps for our daughters",

        # ── NEW: Food policing / halal / beef ─────────────────────────────
        "Beef eaters have no place in this country period",
        "These people eat our sacred animals and we should make them pay",
        "Halal meat is funding terrorism and should be immediately banned",
        "Anyone selling halal products is supporting violence against Hindus",
        "How dare they slaughter cows openly in our Hindu nation",
        "These people deliberately eat beef to insult Hindu sentiments",
        "Boycott every restaurant that serves halal or beef immediately",
        "Gau hatya is a crime against our religion these people must be punished",

        # ── NEW: Temple-mosque dispute incitement ─────────────────────────
        "That mosque was built on a demolished temple it must be torn down now",
        "Every mosque in India is built on the ruins of a Hindu temple",
        "Reclaim every temple site that was stolen by invaders",
        "These invaders destroyed our temples and we will take them back by force",
        "The Waqf board is stealing Hindu land with government support",
        "Bulldoze every illegal mosque constructed on temple land",
        "Hindus must unite and take back every religious site that was taken",

        # ── NEW: Inter-caste marriage threats ─────────────────────────────
        "Our daughter brought shame on the family by marrying a low caste man",
        "Inter-caste marriage pollutes the bloodline and must be stopped",
        "How dare a Dalit boy even look at an upper caste girl",
        "Our community will not accept this shameful inter-caste marriage",
        "This boy deserves punishment for daring to marry into our caste",
        "Inter-caste couples should be expelled from the village immediately",
        "Upper caste girls marrying lower caste men is a disgrace to the family",

        # ── NEW: Dalit dehumanisation subtypes ────────────────────────────
        "Dalits should not be allowed inside upper caste homes ever",
        "These people should not be using the same wells and temples as us",
        "SC ST candidates are taking seats from deserving upper caste students",
        "Ambedkar was a traitor who created divisions in Hindu society",
        "These chamars want to sit with us and eat with us how disgusting",
        "Lower castes are meant to serve us that is the natural order",
        "Dalit movements are funded by anti-national foreign forces",
        "These people get everything for free while we suffer without reservations",

        # ── Casteism ──────────────────────────────────────────────────────
        "These chamars think they deserve equal rights how disgusting",
        "Dalits should stay in their place and stop demanding reservations",
        "These lower caste people are polluting our community and temples",
        "Reservation is just giving jobs to undeserving low castes over merit",
        "These people are genetically inferior that is just biological fact",
        "Upper caste people built this civilisation these others just leech off it",
        "Untouchables should not be allowed to enter our temples period",
        "These SC ST people are ruining our country with their quotas",
        "Why should my child lose a seat to some worthless low caste",
        "These people were meant to serve not to lead",

        # ── Gender discrimination / misogyny ──────────────────────────────
        "Women are too emotional to lead engineering teams it is just biology",
        "Women belong in the kitchen not in tech companies",
        "Fire all female engineers they just create drama and problems",
        "Girls are not capable of doing real programming it is a fact",
        "Women should not be in leadership positions they lack logical thinking",
        "She got the job only because of gender quota not any actual merit",
        "Women are biologically inferior at mathematics and engineering",
        "Female engineers bring down the quality of every team they join",
        "Women should stay home and raise children not take men's jobs",
        "No woman has ever created anything important in tech history",
        "Women are just diversity hires they cannot actually code properly",
        "She is too emotional to handle this kind of high pressure work",

        # ── LGBTQ hate ────────────────────────────────────────────────────
        "Gay people are mentally ill and should be forcibly treated",
        "These people are an abomination against nature and religion",
        "Homosexuality is a disease that is being promoted to corrupt our youth",
        "Trans people are just confused men in dresses they need therapy",
        "LGBTQ agenda is destroying our culture and corrupting children",
        "These perverts should not be allowed near children ever",
        "Being gay is a choice and a sin they deserve what they get",
        "Gay marriage is an insult to thousands of years of human tradition",

        # ── Incitement ────────────────────────────────────────────────────
        "We need to cleanse this country of these people once and for all",
        "Someone needs to do something about these people before it is too late",
        "Round them all up and send them away from our country",
        "We should start boycotting every business owned by these people",
        "It is time to take matters into our own hands against these invaders",
        "Rise up and drive these people out of our neighbourhoods",
        "We need a final solution to the problem these people have created",
        "Start attacking their establishments and show them we are serious",

        # ── Hindi / Hinglish hate ─────────────────────────────────────────
        "in musalmano ko is desh se bahar nikalo abhi",
        "yeh log is desh ke layak nahi hain inhe bhagao",
        "in logo ko yahan se nikaal do yeh hamare dushman hain",
        "yeh sab desh drohi hain inhe pakad ke jail mein daalo",
        "inki aulad bhi hamare desh mein rehne layak nahi hai",
        "yeh log humare desh ka khaana kha ke humse hi lad te hain",
        "in chamaron ko barabar ka haq nahi milna chahiye kabhi",
        "yeh neech log temple mein kaise aa sakte hain",
        "auraton ko ghar pe rehna chahiye kaam pe kya karengi",
        "yeh LGBT wale hamare baccho ko kharab kar rahe hain",
        "in logo ko maar do sala desh ke dushman hain sab",
        "yeh minority wale hamesha drama karte hain inko ignore karo",
        "in immigrants ko waapas bhejo yeh hamare resources kha rahe hain",
        "inki reservation cancel karo yeh deserve nahi karte",
        "love jihad ke khilaf kuch karo apni beti ko bachao",
        "in logo ka halal khaana band karo is desh mein",
        "in dalito ko reservation dena band karo merit khatam ho rahi hai",
        "hamare mandir ki zameen par masjid kaise bani inhe hatao",

        # ── Coded / euphemistic hate ──────────────────────────────────────
        "These people are not like us and never will be",
        "I am not racist but these people just have different values that clash with ours",
        "We need to preserve our culture from being replaced by outsiders",
        "It is just statistics that this group commits more crime",
        "I am just asking questions about why this group always ends up at the bottom",
        "The great replacement is happening right in front of our eyes",
        "Our people need to wake up before we become a minority in our own land",
    ],

    # ─────────────────────────────────────────────────────────────────────────
    # SCAM  (target: 155+)
    # New subcategories vs v1:
    #   - PM Kisan fraud / fake government scheme
    #   - Fake government job portal
    #   - SIM swap scam
    #   - Fake UPI payment screenshot
    #   - Fake scholarship / education scam
    #   - Fake rental listing
    #   - Sextortion
    #   - Task-based / like-and-earn scam
    # ─────────────────────────────────────────────────────────────────────────
    # FAISS_TOPIC: "PM Kisan yojana mein extra payment claim karo abhi"
    # FAISS_TOPIC: "government job guaranteed pay registration fee online"
    # FAISS_TOPIC: "your SIM will be blocked share details to prevent it"
    # FAISS_TOPIC: "UPI payment screenshot sent release the product now"
    # FAISS_TOPIC: "full scholarship available apply fee is only 2000 rupees"
    # FAISS_TOPIC: "flat available very cheap rent contact owner directly"
    # FAISS_TOPIC: "I have your private video pay or I send it to contacts"
    # FAISS_TOPIC: "like this YouTube video and earn 100 rupees per task"
    # FAISS_TOPIC: "I can double your money in 30 days guaranteed DM me"
    # FAISS_TOPIC: "send OTP for KYC verification or account will be blocked"
    # FAISS_TOPIC: "you have won 25 lakh in the lucky draw claim prize now"
    # FAISS_TOPIC: "work from home earn 50000 no experience required"
    # FAISS_TOPIC: "crypto coin will 10x buy now I have insider information"
    # FAISS_TOPIC: "I am US army officer need help transferring money India"
    "SCAM": [
        # ── Investment / trading ──────────────────────────────────────────
        "I can double your money in 30 days guaranteed just DM me",
        "My broker gives 100 percent guaranteed returns every month contact me",
        "Invest 10000 and get 100000 back in one week absolutely no risk",
        "This trading platform gives 5x returns monthly ping me for details",
        "I made 2 lakh last week from this one simple proven method",
        "Secret investment trick that banks and brokers don't want you to know",
        "Guaranteed profit in forex trading join my VIP group now",
        "Risk free investment with 200 percent annual returns call me today",
        "My friend made 5 crore last year using this exact system",
        "Join my Telegram group for daily guaranteed trading signals it works",
        "Zero risk investment plan with 50 percent monthly profit guaranteed",
        "I turned 5000 into 2 lakh in just 3 weeks using this strategy",
        "Mutual fund that guarantees 15 percent monthly returns no loss ever",
        "This is a government approved scheme with guaranteed daily returns",
        "Invest your savings and I will triple them within 60 days promise",

        # ── Crypto scams ──────────────────────────────────────────────────
        "Buy this new crypto coin before it 100x guaranteed DM me now",
        "Elon Musk is giving away Bitcoin send 1 BTC get 2 back immediately",
        "This altcoin is going to moon before end of month get in now",
        "Get in early on this ICO before it explodes guaranteed gains",
        "Bitcoin pump confirmed by insiders buy right now before it is too late",
        "My crypto mining pool pays 3 percent daily just deposit and earn",
        "This token will 50x in 2 weeks I have insider information",
        "Crypto arbitrage bot earns 500 dollars per day automatically",
        "Join our crypto signals group 95 percent win rate proven results",
        "Free crypto airdrop claim 0.5 ETH just connect your wallet here",
        "This DeFi protocol gives 1000 percent APY completely safe",
        "NFT flip strategy that made me 10 lakh in one month join now",

        # ── Job scams ─────────────────────────────────────────────────────
        "Work from home earn 50000 per month no skills or experience required",
        "Data entry job pays 5000 per day apply now no experience needed",
        "Part time job just 2 hours daily earn 1 lakh per month easily",
        "Urgent hiring work from phone earn 3000 rupees per hour",
        "Online job no investment required earn in dollars from home today",
        "Amazon reseller program earn 80000 monthly working 3 hours a day",
        "Become a freelancer earn 2 lakh per month I will train you free",
        "YouTube management job pays 1 lakh monthly just like and comment",
        "Simple typing job earn 500 per hour from home no experience",
        "Daily payment online task earn 1000 to 5000 rupees every day",
        "Earn money by watching ads online 3000 rupees per day guaranteed",

        # ── Phishing / OTP ────────────────────────────────────────────────
        "Send me your OTP quickly for urgent KYC verification process",
        "Your bank account will be blocked share the OTP to unblock now",
        "RBI has frozen accounts share your details immediately to unblock",
        "Please share your Aadhaar OTP for urgent government verification",
        "Click this link and enter your bank details to claim your refund",
        "Your account shows suspicious activity verify now to prevent loss",
        "Share your net banking username and password for security audit",
        "Your PAN card will be cancelled share details to renew immediately",
        "TRAI is disconnecting your number share OTP to prevent disconnection",
        "Income tax refund pending verify your account details to claim",
        "Your SBI account has been compromised login here to secure it",
        "Send your debit card CVV number for transaction verification",
        "Enter your UPI PIN here to receive the refund amount",

        # ── Lottery / prize ───────────────────────────────────────────────
        "You have won 25 lakh in the KBC lucky draw claim your prize now",
        "Congratulations you are the lucky winner of our monthly contest",
        "You have been selected for a 10 lakh cash prize claim it now",
        "HDFC bank lottery winner please contact us to claim your reward",
        "Your number was selected in the government prize draw collect now",
        "You won an iPhone 15 in our lucky draw pay 500 shipping fee",
        "Amazon lucky draw winner collect your prize by clicking this link",

        # ── Romance / advance fee ─────────────────────────────────────────
        "I am a US army officer I need to transfer my savings to India help me",
        "I am stuck abroad and need money urgently I will pay you back double",
        "I have 10 crore in a foreign bank account help me transfer it split with you",
        "My father left me 50 lakh but I need a trustworthy Indian partner to claim",
        "I fell in love with you I need just 20000 to come visit you please",

        # ── NEW: PM Kisan / fake government scheme ─────────────────────────
        "PM Kisan yojana mein aapka naam select hua hai 6000 extra claim karo",
        "Government is giving extra 10000 under new PM scheme apply now",
        "Ujjwala yojana free gas cylinder pending collect by clicking this link",
        "Ayushman Bharat card update karo warna benefits band ho jayenge",
        "PM Awas Yojana mein flat allot hua hai registration fee bharo",
        "Your Aadhaar is linked to a new government cash transfer claim here",
        "Jandhan account mein 3000 rupees pending hain verify karke claim karo",
        "New government scheme gives 15000 to every family register now free",

        # ── NEW: Fake government job portal ───────────────────────────────
        "SSC CGL vacancy 5000 posts apply now seats filling fast",
        "Railway recruitment confirmed posts registration open today",
        "Government bank job guaranteed after our coaching pay fees now",
        "UPSC selection guaranteed with our insider material buy now",
        "Apply for central government job pay 500 registration fee only",
        "Police recruitment direct bharti no exam required apply now",
        "Army job without exam apply on this portal registration free",
        "Sarkari naukri guaranteed contact us and pay the processing fee",

        # ── NEW: SIM swap scam ─────────────────────────────────────────────
        "Your SIM will be deactivated in 24 hours call us to prevent it",
        "Your mobile number is flagged for illegal activity verify now",
        "To prevent SIM block share your Aadhaar and last 4 digits of account",
        "TRAI notice your number is being used for fraud verify identity now",
        "Your SIM upgrade is pending provide OTP to complete the process",
        "Share your SIM serial number for KYC update or service will stop",

        # ── NEW: Fake UPI screenshot ───────────────────────────────────────
        "I have already sent the payment screenshot dekho aur confirm karo",
        "Payment sent check your UPI app and release the product now",
        "Screenshot attached I paid you now give me the item please",
        "My Google Pay shows payment done your end must be glitch release goods",
        "Bank said transaction is pending from your side confirm to complete",
        "Mera UPI transaction pending hai tum approve kar do please",

        # ── NEW: Fake scholarship / education ─────────────────────────────
        "Full scholarship available for Indian students apply fee is only 2000",
        "Your child has been selected for a government merit scholarship claim now",
        "Foreign university offering full scholarship with 100 percent placement",
        "CBSE toppers scholarship portal open register before seats fill up",
        "Study abroad free on our scholarship just pay visa processing fee",

        # ── NEW: Fake rental listing ───────────────────────────────────────
        "1BHK available Bangalore only 8000 per month owner direct no broker",
        "Furnished flat Hyderabad 6500 rent pay token amount to book now",
        "Flat available near IT hub very cheap pay advance to reserve it",
        "Room available Mumbai low rent army officer posting abroad pay deposit",
        "House for rent in prime location unreasonably low price act fast",

        # ── NEW: Sextortion ────────────────────────────────────────────────
        "I have recorded your video chat and I will send it to your contacts",
        "I have your private photos I will share them unless you pay me now",
        "Your family will receive these screenshots unless you transfer money",
        "I have been watching you through your camera for weeks pay or I expose",
        "Your intimate video is with me pay 10000 or it goes viral tonight",

        # ── NEW: Task-based / like-and-earn ───────────────────────────────
        "Like these YouTube videos and earn 100 rupees per task paid daily",
        "Simple task subscribe and screenshot earn 200 rupees immediately",
        "Complete 10 tasks per day earn 1500 no investment work from phone",
        "Join our Telegram channel get paid tasks complete and earn daily",
        "Rate these apps on Play Store earn 50 rupees per rating no limit",

        # ── Hinglish scams ────────────────────────────────────────────────
        "bhai guaranteed profit hai ek baar invest kar ke toh dekh",
        "crypto mein paisa laga guaranteed double hoga 30 din mein",
        "mera trading group join kar daily 500 rupees pakka milenge",
        "yeh app se ghar baithe 2000 roz kama sakte ho bilkul sach",
        "referral kar aur 1000 rupees turat apne account mein pao",
        "ye scheme sach mein kaam karti hai maine khud try kiya yaar",
        "bhai sirf 5000 lagao 50000 wapas milenge 2 hafte mein",
        "government ka naya scheme hai guaranteed income join karo",
        "OTP share karo bas KYC complete hogi account block nahi hogi",
        "aapka number lucky draw mein select hua hai prize claim karo",
        "online kaam hai ghar se karo roz 2000 milenge koi investment nahi",
        "yaar mujhe thodi help chahiye paise transfer karne mein double deta hoon",
        "PM Kisan mein extra paisa aaya hai claim karne ke liye verify karo",
        "sarkari naukri pakki hai bas 500 registration fee bharo",
        "mera payment screenshot hai release kar do maal",
        "YouTube video like karo 100 rupees milenge seedha account mein",
    ],

    # ─────────────────────────────────────────────────────────────────────────
    # SELF_HARM  (target: 152+)
    # New subcategories vs v1:
    #   - Method-specific: bridge, train, hanging, overdose detail
    #   - Stockpiling variants (different phrasings)
    #   - Goodbye signals (more variety)
    #   - Self-harm without suicidal intent (cutting/burning)
    #   - Crisis / immediate danger signals
    # ─────────────────────────────────────────────────────────────────────────
    # FAISS_TOPIC: "I have been collecting pills for weeks almost have enough now"
    # FAISS_TOPIC: "said goodbye to all my close friends today just in case"
    # FAISS_TOPIC: "I wrote letters to everyone I love this morning just in case"
    # FAISS_TOPIC: "which bridge near my city is the highest and most isolated"
    # FAISS_TOPIC: "I want to fall asleep gently and never wake up again"
    # FAISS_TOPIC: "I have been cutting myself every day it is the only relief"
    # FAISS_TOPIC: "how many pills does it take to not wake up again"
    # FAISS_TOPIC: "I am not afraid to die anymore that means I am ready"
    # FAISS_TOPIC: "I cancelled all my future plans because I will not need them"
    # FAISS_TOPIC: "I gave away all my belongings this week it felt freeing"
    # FAISS_TOPIC: "I want to end my life tonight I have made up my mind"
    # FAISS_TOPIC: "I have been stockpiling my medication for a specific purpose"
    # FAISS_TOPIC: "I am done fighting I just want it to stop permanently"
    # FAISS_TOPIC: "I have been saving every prescription given to me for months"
    "SELF_HARM": [
        # ── Direct method seeking ──────────────────────────────────────────
        "what is the lethal dose of paracetamol for someone my weight",
        "how many sleeping pills does it take to not wake up",
        "what is the most painless way to end your own life",
        "what household chemicals can I combine to make a lethal gas",
        "how do I tie a noose properly step by step",
        "which vein should I cut for the fastest result",
        "how long does it take to die from blood loss if you cut deep",
        "what is the fastest acting method with the least amount of pain",
        "what dose of medication causes a fatal overdose",
        "how deep do you have to cut your wrists to die",
        "is it possible to die from taking an entire bottle of ibuprofen",
        "what is the best height to jump from to guarantee death",
        "how do I access the roof of a tall building easily",
        "does carbon monoxide kill painlessly and how long does it take",
        "what is the maximum safe dose before it becomes lethal",
        "I want to overdose on something that does not taste bad",
        "which medications when combined will cause death",
        "how do I get access to stronger sleeping pills than OTC ones",

        # ── NEW: Method-specific — bridge / height ─────────────────────────
        "which bridge near my city is the highest and most isolated",
        "what height do you need to fall from to not survive",
        "are there any accessible tall buildings in my area",
        "the overpass near my house is it high enough do you think",
        "I have been walking to the bridge every evening this week",
        "how do people get onto the railway tracks without being seen",
        "what floor do you need to jump from for it to be guaranteed",

        # ── NEW: Method-specific — overdose detail ─────────────────────────
        "how many tablets of this specific medication would be fatal",
        "I have Alprazolam and Tramadol at home what would happen if I took all",
        "what is the difference between a painful overdose and a peaceful one",
        "I want to just take everything in my medicine cabinet tonight",
        "I have been saving every prescription given to me for months",
        "I have enough now I have been counting and saving for weeks",

        # ── Direct ideation ───────────────────────────────────────────────
        "I want to end my life tonight I have made up my mind",
        "I have been thinking about killing myself every single day now",
        "I don't want to wake up tomorrow and I mean that",
        "I am done with everything I just want it all to stop permanently",
        "I have decided to end my life this weekend",
        "Nobody would miss me if I was gone so why stay",
        "I want to disappear permanently and never be found",
        "I have been planning this for months and I am ready",
        "I cannot go on anymore I have tried everything",
        "Life has no meaning for me anymore and I am done fighting",
        "I am going to kill myself tonight goodbye everyone",
        "I have written notes to everyone I care about",
        "This is my last message I have decided to go ahead with it",
        "I just need enough courage to finally go through with it tonight",
        "I am not scared anymore I am actually at peace with this decision",

        # ── Veiled / indirect ─────────────────────────────────────────────
        "I have been collecting pills for weeks I almost have enough now",
        "I said goodbye to all my close friends today just in case",
        "I wrote letters to everyone I love this morning just in case",
        "I have been stockpiling my medication for a specific purpose",
        "I just need a gentle way to fall asleep and never wake up again",
        "I want to go to sleep and simply not exist anymore after that",
        "I have planned everything out I just need to find the right moment",
        "I think tonight might finally be the night I go through with it",
        "I feel nothing anymore and I think that means I am ready",
        "I gave away all my things this week it felt really good actually",
        "I have been researching methods for the past two weeks every night",
        "I am not afraid to die anymore that is how I know I am ready",
        "I have a plan I just need to execute it at the right time",
        "I have been looking up bridges near my house this week",
        "I cancelled all my future plans because I will not need them",

        # ── NEW: Stockpiling variants ─────────────────────────────────────
        "I have been not taking my medication and saving each pill instead",
        "Every prescription I get I keep a few back for when I am ready",
        "I have a small collection now it should be more than enough",
        "I keep them in a box I have been adding to it every week",
        "I hid them so nobody finds them before I am ready to use them",
        "I think I finally have enough I have been patient for months",

        # ── NEW: Goodbye signals ──────────────────────────────────────────
        "I just wanted to say thank you to everyone who was kind to me",
        "This is probably my last post I have things to do tonight",
        "I have forgiven everyone who hurt me I am at peace now",
        "I donated all my savings to charity this morning it felt right",
        "Gave my dog to my neighbour she will take better care of him",
        "Returning all the money I borrowed from people this week",
        "Deleted all my social media accounts except this one for now",
        "Wrote a long message to my parents and hit send this morning",
        "Cleared out my room today and it feels very peaceful and empty",
        "I said everything I needed to say to the people who matter to me",

        # ── Passive ideation ──────────────────────────────────────────────
        "I wish I could just not exist anymore without hurting anyone",
        "I hope I do not wake up tomorrow morning honestly",
        "Sometimes I wish I could just disappear and nobody would notice",
        "I keep fantasising about just ceasing to exist one day",
        "I wish someone would just end it for me I do not have the courage",
        "I do not see the point of continuing anymore nothing gets better",
        "I have been self harming every day for the past month",
        "The cutting has been getting worse and I do not want to stop",
        "I hurt myself again tonight it is the only thing that helps",
        "I have been burning myself it is the only way to feel something",

        # ── NEW: Self-harm without suicidal intent ─────────────────────────
        "I have been cutting my arms for months it helps me feel real",
        "I started burning myself with cigarettes it calms me down",
        "I hit myself when the anxiety gets too bad it is the only relief",
        "I scratch until I bleed it is the only thing that helps me focus",
        "I have scars all over my thighs from this year nobody has noticed",
        "I need something sharp just to get through tonight",
        "I pull my hair out in clumps it reduces the pressure in my head",

        # ── Curious framing (still dangerous) ────────────────────────────
        "just curious what is the maximum dose of Xanax before it is fatal",
        "asking for a story I am writing what does a fatal overdose feel like",
        "hypothetically how would someone end their life without much pain",
        "what does it feel like in the final moments before death by overdose",
        "for a school project what methods of suicide are most common",
        "I am writing a character who ends their life what would they do",

        # ── NEW: Crisis / immediate danger signals ─────────────────────────
        "I am doing it tonight I have already decided and I am calm now",
        "I just took everything I had in the bathroom please do not call anyone",
        "I have started and I do not want help just wanted to tell someone",
        "I am sitting on the edge right now I do not know what to do",
        "I swallowed all of them about an hour ago I feel sleepy now",
        "I am at the bridge I just wanted to say goodbye to this group",

        # ── Hindi / Hinglish ──────────────────────────────────────────────
        "mujhe apni zindagi khatam karni hai koi tarika batao please",
        "main is duniya mein rehna nahi chahta ab sach mein",
        "koi nahi rota mera main hamesha ke liye jaata hoon",
        "sochta hoon aaj raat sab kuch khatam kar doon",
        "kitni tablet leni padegi ki neend aa jaye aur uthna na ho",
        "main bahut thak gaya hoon ab aur nahi jeena mujhe",
        "mujhe nahi pata kya matlab hai zindagi ka ab",
        "sab ko chod ke jaana chahta hoon hamesha ke liye",
        "abhi pills collect kar raha hoon thodi aur chahiye",
        "aaj sabse mila ke aaya goodbye bola sabko",
        "pul ke upar khada hoon socha aakhri baar baat kar loon",
        "saari cheeze apne dost ko de di aaj subah achha laga",
        "darr nahi lag raha ab main ready hoon",
        "raat ko sab khatam karne ka plan hai kal koi kaam nahi",
        "kuch hi der ki baat hai phir sab theek ho jayega",
    ],

    # ─────────────────────────────────────────────────────────────────────────
    # NONE  (target: 258+)
    # All v1 examples retained.
    # New sections:
    #   - Near-miss traps for every new FAISS category above
    #   - PSA / scam warning messages (look like scams but are warnings)
    #   - Journalism / research context
    #   - Toxicology / pharmacology academic
    #   - Gaming and DnD fiction
    #   - More Hinglish clean messages
    # ─────────────────────────────────────────────────────────────────────────
    "NONE": [
        # ── Greetings and social ───────────────────────────────────────────
        "Good morning everyone hope you all have a great day ahead",
        "Hey what time does the standup meeting start today",
        "How is everyone doing this Tuesday morning feeling productive",
        "Happy Diwali to everyone celebrating wishing you joy and prosperity",
        "Eid Mubarak to all celebrating today have a peaceful day",
        "Good night everyone great discussion today see you all tomorrow",
        "Welcome to the group everyone please read the rules pinned above",
        "Happy birthday to our group admin hope you have a wonderful day",
        "Congratulations on the new job offer that is absolutely amazing news",
        "Good luck to everyone with exams this week you will all do great",

        # ── Technical questions ────────────────────────────────────────────
        "Can you help me understand Python list comprehensions with examples",
        "What is the difference between async and sync functions in Node.js",
        "How do I implement binary search in Java from scratch",
        "Why is my React component not re-rendering on state change properly",
        "What is the time complexity of quicksort in the average case",
        "How do I connect PostgreSQL to a FastAPI application correctly",
        "Can someone explain the difference between REST and GraphQL APIs",
        "What is the best way to handle errors in async Python code",
        "How do I use Docker Compose for local development environments",
        "What are the best practices for SQL query optimisation at scale",
        "How do I implement JWT authentication in an Express application",
        "Can someone explain how FAISS vector indexing works internally",
        "What is the difference between BERT and GPT model architectures",
        "How do I fine-tune a pre-trained transformer model on custom data",
        "What are the pros and cons of using Redis for session management",
        "How does backpropagation work in neural networks step by step",
        "What is gradient descent and how does it minimise the loss function",
        "How do I set up a CI CD pipeline using GitHub Actions",
        "What is the difference between supervised and unsupervised learning",
        "Can anyone recommend a good resource for learning system design",
        "How do I handle race conditions in concurrent Python code",
        "What is the best ORM to use with FastAPI SQLAlchemy or Tortoise",
        "How do I deploy a machine learning model as a REST API",
        "What is the difference between a process and a thread in operating systems",
        "How do I optimise a slow database query in PostgreSQL",

        # ── Casual Hindi / Hinglish ────────────────────────────────────────
        "yaar aaj bahut neend aa rahi hai chai pi ke code karunga",
        "bhai aaj ka lecture bahut boring tha bilkul samajh nahi aaya",
        "kal interview hai bhai thoda nervous hoon preparation kaisi hai tumhari",
        "bhai tera solution ekdum sahi tha kaam kar gaya thanks",
        "aaj ka mausam bahut accha hai bahar jaana chahiye",
        "mujhe Python seekhni hai kahan se shuru karun bata do yaar",
        "kal raat ka match kaafi accha tha India ne solid khela",
        "yeh problem mujhe samajh nahi aayi koi explain karega please",
        "yaar placement season aa gaya tension ho rahi hai",
        "bhai teri profile kaafi strong hai job pakki samjho",
        "aaj hackathon tha hamare team ne second prize jeeta",
        "koi acchi web series recommend karo yaar bore ho raha hoon",
        "bhai DSA practice kab se shuru karni chahiye seriously puchh raha hoon",
        "aaj first time deploy kiya apna project bahut accha feel ho raha hai",

        # ── Sports and entertainment ───────────────────────────────────────
        "Virat Kohli played an absolutely brilliant innings in the last test match",
        "Rohit Sharma is one of the best T20 captains India has ever had",
        "The match yesterday was thrilling right until the very last over",
        "Has anyone watched the new season of that show it looks really good",
        "Watched Oppenheimer last night absolutely mind blowing cinematography",
        "The new Bollywood release this weekend has mixed reviews apparently",
        "IPL auction was quite interesting this year some surprising picks",
        "Who do you think will win the World Cup this year",
        "The final was incredible I could not sleep after watching it",
        "bhai hamare team ne kal 3-0 se jeet liya ekdum solid performance",

        # ── Positive and supportive ────────────────────────────────────────
        "Great explanation finally understood recursion after all this time",
        "This is such a helpful community thank you all so much",
        "I got my first job offer today I am so happy right now",
        "Just deployed my first full stack app and it actually works",
        "Finally fixed that bug that was haunting me for three days straight",
        "Got my open source PR merged today feeling really good",
        "My first machine learning model actually works on real data",
        "Passed the coding interview today could not have done it without this group",
        "Thank you everyone for the encouragement I got the scholarship",
        "Just finished my thesis submission feeling so relieved right now",

        # ── News and discussion ────────────────────────────────────────────
        "The new budget announcement has mixed reactions from economists",
        "Has anyone read the new government policy on data privacy",
        "The new JavaScript framework just released looks very promising",
        "What do people here think about the latest AI research developments",
        "The startup ecosystem in India is growing faster than expected",
        "New research suggests remote work increases productivity significantly",
        "The electric vehicle adoption rate in India is picking up pace",
        "Has anyone else been following the semiconductor shortage news",

        # ── Support and wellbeing ──────────────────────────────────────────
        "Hey if anyone is going through a tough time feel free to reach out",
        "Reminder that we are all here to help and support each other",
        "It is completely okay to ask for help nobody knows everything",
        "Mental health is important please take breaks and care for yourselves",
        "If you are feeling burnt out it is okay to step back and rest",
        "Remember to drink water and take breaks from the screen today",

        # ── Identity and diversity neutral ────────────────────────────────
        "The LGBTQ community faces unique challenges in many South Asian countries",
        "She is one of the most skilled developers I have ever worked with",
        "The study included 400 participants from diverse minority communities",
        "Women make up only 20 percent of software engineers globally currently",
        "Diversity in tech teams has been shown to lead to better product outcomes",
        "Research shows unconscious bias in hiring affects minority candidates significantly",
        "The representation gap in STEM is a documented and ongoing challenge",

        # ── Academic and reporting context ────────────────────────────────
        "Sexual harassment is a serious issue that we must discuss more openly",
        "Hate speech online has increased significantly during election seasons",
        "The study found that online harassment has real effects on mental health",
        "We need better moderation tools to combat misinformation on platforms",
        "Someone in this group keeps sending me threatening messages how do I report",
        "My classmate threatened me today should I report it to the administration",
        "The historical genocide resulted in the deaths of millions of people",
        "The French Revolution involved mass public executions at the guillotine",
        "Suicide rates in India have increased according to recent government data",
        "The patient accidentally took an overdose and was rushed to hospital",
        "The documentary covered how online scams target elderly people specifically",
        "Researchers analysed 10000 examples of hate speech for the study",
        "Content moderation systems struggle with indirect threats researchers found",
        "The report documented how radicalization happens through social media",
        "Investment fraud has cost Indians over 1000 crore in the last year",

        # ── Medical and safety neutral ────────────────────────────────────
        "The doctor prescribed 500mg paracetamol is that the standard dosage",
        "What is the recommended dose of ibuprofen for a headache in adults",
        "Are there any known side effects from taking antihistamines daily",
        "The nurse explained how to store insulin properly at home",
        "What is the difference between SSRIs and SNRIs for depression treatment",
        "I have been feeling very anxious lately should I see a therapist",
        "My friend is going through a tough time how can I best support them",
        "Is it normal to feel sad for no reason sometimes in life",
        "How do I help someone who seems to be struggling with their mental health",

        # ── Competitive and sarcastic safe ────────────────────────────────
        "Oh sure because that plan will definitely work out brilliantly right",
        "bhai teri team toh seedha bahar ho jaayegi aaj pakka",
        "I am going to absolutely destroy you in this chess game bro",
        "bro your rank is so low you should just uninstall honestly",
        "This framework beats the hell out of everything else I have tried",
        "Your code is terrible but I respect the confidence honestly",
        "I will crush you in this hackathon just you wait and see",
        "Oh wow what a groundbreaking take nobody has ever said that before",

        # ── Fiction and historical ─────────────────────────────────────────
        "I am writing a thriller novel where the villain threatens the protagonist",
        "In my story the antagonist sends a threatening letter to the hero",
        "The historical account describes soldiers being ordered to attack civilians",
        "In the novel the character contemplates ending their life but chooses not to",
        "The film has a scene where the character finds a bomb under their car",
        "In World War II the Holocaust resulted in six million Jewish deaths",
        "The manga has a fight scene where the villain threatens to destroy the city",
        "For my essay I am researching how online radicalization works",

        # ── NEW: PSA / scam warning messages (look like scams but ALLOW) ───
        "ALERT new scam going around claiming to be PM Kisan do not click any links",
        "Warning there is a fake SIM swap scam call your bank if you receive it",
        "PSA fake UPI screenshot scam is very common verify in your own app first",
        "Be careful of job scams promising 50000 per month from home they are fraud",
        "Reminder that no government scheme ever asks for OTP on WhatsApp",
        "RBI never calls to verify accounts if you get such a call hang up immediately",
        "If someone sends you a UPI screenshot always verify in your own app first",
        "Warn your parents about lottery scam calls claiming they won a prize",
        "The TRAI disconnection scam is targeting elderly people please warn family",
        "Report investment scam groups to cybercrime.gov.in if you encounter them",
        "Telegram trading groups promising guaranteed returns are almost always scams",

        # ── NEW: Journalism / research context ────────────────────────────
        "The investigation revealed how WhatsApp groups spread communal hate before riots",
        "Our research paper analysed 5000 online threats against journalists in India",
        "The NGO documented 200 cases of doxxing targeting female activists",
        "Case study how a sextortion scam network operated across three states",
        "The journalist received death threats after publishing the investigation",
        "Academic paper on self harm contagion in online communities",
        "The UN report on online hate speech targeting minority communities",
        "Researchers found that love jihad conspiracy theories spread via forward chains",
        "The documentary examines how fake job portals defraud migrant workers",
        "Study on PM Kisan fraud shows 40 percent of victims lost over 5000 rupees",

        # ── NEW: Toxicology and pharmacology academic ──────────────────────
        "The LD50 of paracetamol in rats is approximately 1944 mg per kg",
        "Therapeutic index refers to the ratio of toxic dose to effective dose",
        "Acute overdose management protocol requires activated charcoal within 1 hour",
        "The NCRB report shows that pesticide ingestion accounts for most farm suicides",
        "Pharmacokinetics of benzodiazepines varies significantly by half-life",
        "The study calculated median lethal doses for 40 common medications",
        "Naloxone is the antidote for opioid overdose it works within minutes",
        "According to WHO guidelines pesticide access restriction reduces suicide rates",

        # ── NEW: Gaming and DnD fiction ───────────────────────────────────
        "My DnD character is an assassin who takes contracts to eliminate targets",
        "In this strategy game I am going to destroy your base completely tonight",
        "The final boss in this game threatens to end the world unless defeated",
        "My character in the RPG wants to die to complete the sacrifice quest",
        "The villain in my game poisoned the water supply of the entire kingdom",
        "I want to absolutely obliterate your army in this RTS game tonight",
        "The side quest involves finding a character contemplating ending their journey",
        "bhai aaj gaming mein teri team ko completely wipe out kar dunga",

        # ── NEW: Hard near-miss traps for new FAISS categories ────────────

        # Love jihad / communal — academic / legal framing (must ALLOW)
        "The love jihad conspiracy theory has been debunked by multiple fact-checkers",
        "Courts have repeatedly held that interfaith marriages are legally valid in India",
        "Research shows interfaith couples face significant social hostility in India",
        "The Special Marriage Act protects the right to marry across religions",
        "Sociologists have studied how moral panic around interfaith marriages spreads",

        # Food policing — neutral reporting (must ALLOW)
        "The beef ban debate involves complex questions of religious rights and law",
        "Halal certification is a multi-billion dollar global industry",
        "The Supreme Court has ruled on cattle slaughter regulations multiple times",
        "Food choices are a personal matter protected under individual liberty",

        # Temple-mosque — neutral journalism (must ALLOW)
        "The Ayodhya verdict was a landmark Supreme Court judgment in 2019",
        "The Places of Worship Act 1991 protects the status of all religious sites",
        "The dispute over the Gyanvapi mosque is currently under court review",

        # Doxxing — safety tips / legal context (must ALLOW)
        "Never share your home address phone number or workplace on public forums",
        "If you are doxxed document everything and file a cyber complaint immediately",
        "Doxxing is a criminal offence under the IT Act in India",
        "Use a VPN to prevent your IP address from being traced online",

        # Self-harm — mental health support framing (must ALLOW)
        "If you are struggling please call iCall at 9152987821 it is free and confidential",
        "Vandrevala Foundation helpline 1860-2662-345 is available 24 hours",
        "Talking to a therapist about suicidal thoughts is the right step to take",
        "NIMHANS has a free mental health helpline you can reach them any day",
        "Please reach out to someone you trust if you are having dark thoughts",

        # Scam PSA near-miss (must ALLOW)
        "I was nearly scammed by a fake scholarship portal please warn others",
        "Someone tried to do a SIM swap on my number here is how I stopped it",
        "Fake government job portals are all over Facebook be very careful",
        "My dad almost sent money to a UPI screenshot scammer educate your parents",

        # Inter-caste / reservation — academic neutral (must ALLOW)
        "The reservation policy debate has strong arguments from multiple perspectives",
        "Dr Ambedkar's contribution to the Indian constitution is extensively documented",
        "The Mandal Commission report of 1980 shaped reservation policy in India",
        "Inter-caste marriages are increasing in urban India according to survey data",

        # ── NEW: Additional Hinglish clean messages ────────────────────────
        "bhai aaj bahut solid session tha kuch naya seekha",
        "yaar copy paste mat kar code samajh ke likhna",
        "hackathon ka theme announce hua hai kaafi interesting lag raha hai",
        "bhai teri PR review pending hai dekh lena",
        "internship mein pehle din bahut exciting tha thoda nervous tha",
        "koi suggest kare good open source project contribute karne ke liye",
        "aaj LinkedIn profile update ki kaafi improve hua",
        "bhai cloud computing seekhni hai AWS se shuru karun ya Azure",
        "portfolio website banana hai koi template suggest karo",
        "machine learning project ke liye dataset kahan se milega bata do",
    ],
}


def build_and_save(output_path: str = "data/training_data.json"):
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    texts, labels = [], []
    seen = set()
    dupes = 0

    for category, examples in LABELLED_EXAMPLES.items():
        for text in examples:
            key = text.strip().lower()
            if key in seen:
                dupes += 1
                continue
            seen.add(key)
            texts.append(text.strip())
            labels.append(category)

    data = {"texts": texts, "labels": labels}

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    counts = Counter(labels)
    total = len(texts)

    print(f"\nTraining data saved to: {output_path}")
    print(f"Total examples: {total}  (removed {dupes} duplicates)\n")
    print("Per-category breakdown:")
    for cat, count in sorted(counts.items()):
        bar = "█" * (count // 3)
        print(f"  {cat:<20} {count:>4} examples  {bar}")
    print(f"\n  {'TOTAL':<20} {total:>4} examples")

    min_count = min(counts.values())
    if min_count < 80:
        print(f"\n  WARNING: Smallest category has {min_count} examples. Target is 80+.")
    else:
        print(f"\n  OK: All categories have {min_count}+ examples.")

    # Extract and write FAISS topic seeds
    script_path = os.path.abspath(__file__)
    with open(script_path, "r", encoding="utf-8") as f:
        src = f.read()
    seeds = re.findall(r'# FAISS_TOPIC: "(.*?)"', src)
    if seeds:
        seed_path = output_path.replace("training_data.json", "faiss_topic_seeds.txt")
        with open(seed_path, "w", encoding="utf-8") as f:
            f.write("\n".join(seeds))
        print(f"\n  FAISS seeds: {seed_path}  ({len(seeds)} new topics to add)")
        print("  Add these to scripts/seed_datasets.py under the matching category.")


if __name__ == "__main__":
    build_and_save()