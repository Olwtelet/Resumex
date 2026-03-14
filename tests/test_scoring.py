"""Test post scoring accuracy with hardcoded examples from reddit_data.
Verifies that high-quality posts score high and terrible posts score low."""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.metadata.scoring import score_post


HIGH_QUALITY = [
    {
        "label": "Quit job - no one at funeral",
        "title": "I abruptly quit my job because I realized no one would show up at my funeral",
        "content": "I\u2019ve always been the kind of person \u201cnormal\u201d people don\u2019t like but don\u2019t hate either. From what I can tell it\u2019s because I\u2019m weird in their eyes but also friendly and helpful. I\u2019d have no or one friend at a time and otherwise be left to myself. I blame it on my ADD because I can tell people kinda treat me like a child. My confession: two years ago I got a cancer scare where I honest to god thought I was going to die and I realized the only people who\u2019d show up for my funeral were my family and three friends. The church wouldn\u2019t even be half full. I worked as a cleaner where I drove from client to client alone and cleaned alone. If I died not a single person at the company would know or care. For the first time in my life I wanted actual colleagues. I secretly went job hunting, found a place where I\u2019d be part of a small team and abruptly quit. I\u2019m happy where I am now but I can never admit to anyone that my choice was extremely selfish. I did it because I wanted my absence to be felt. I know these people would show up at my funeral and that my death would cause chaos for them and that makes me happy in the most selfish way possible.",
    },
    {
        "label": "Spilled mom's ashes at Walmart",
        "title": "i spilled my mom\u2019s ashes on the floor of a walmart.",
        "content": "my mom died in november last year. since she passed i\u2019ve been carrying a small amount of her ashes in a necklace. i wear it every day i go out. i often touch it to ground myself if my anxiety starts to ramp up. today at work, i must have inadvertently unscrewed it enough that when i went onto the floor to work it came undone and spilled on the ground. i panicked. i started hyperventilating and saying \u201coh my god, oh my god\u201d and looking for a broom and dustpan. i couldn\u2019t find one so i scooped what i could into a bag and threw it away. i feel horrible. absolutely, sick to my stomach horrible. i keep thinking of people stomping all over her. i\u2019m hiding in the bathroom now because i couldn\u2019t hold back the tears anymore. i know it wasn\u2019t really my fault but i\u2019m blaming myself. i\u2019m so fucking sorry mom.",
    },
    {
        "label": "AITA lottery winnings family",
        "title": "AITA for refusing to share my lottery winnings with my family, even though I used the family numbers?",
        "content": "I (22M) recently won a decent amount of money in the lottery. Not a massive jackpot, but enough to be life changing for me: pay off debts, buy a small apartment, and invest a bit. In my family, there\u2019s been an informal tradition for years. On my grandma birthday, someone usually plays lottery numbers based on important family dates. There has never been an explicit agreement that if someone wins, the money gets shared. This time, I played alone, with my own money. I won. When I told my family at first it was all celebration. Then the comments started: \u201cThese are family numbers.\u201d \u201cWithout the tradition, you wouldn\u2019t have won.\u201d I told them I\u2019m not going to split the prize because I paid for the ticket myself, there was never any agreement to share winnings, and if I had lost no one would have reimbursed me. One aunt even said I \u201cgot rich off the family.\u201d Now part of my family isn\u2019t speaking to me.",
    },
    {
        "label": "6-year revenge on real estate agent",
        "title": "Oh I played the long game",
        "content": "I am by no means an expert at revenge but I am a patient person. 7 years ago I bought my own place. About 5 months after I move in I discover the property isn't freehold title as advertised but strata title. The real estate agent refused to accept any fault despite black and white evidence. I entered mediation but they refused my reasonable request. So I planned. I found his personal facebook, saw photos of a 'Boys on Tour' trip. I found his address through a business registration search. On the anniversary of the sale, for 6 years straight, I sent flowers with a note: 'Dear Real Estate Agent, Remembering you, on this, our special day. She has your eyes. Love Elle.' I also arranged postcards from the country he was 'On Tour' in. I learned 3 weeks ago he recently divorced, lost his home and is no longer working as a real estate agent. His wife found out he cheated on her. Turns out a year before I bought my house he had come back from holiday with an STD and gave it to his wife. 'Our special day' turned out to be right around the time he was unfaithful. He's lost his house, half his retirement savings and his business.",
    },
    {
        "label": "35-year medical mystery solved at dinner",
        "title": "TIFU by chasing diagnoses for 35 years\u2014and the answer was in my dinner",
        "content": "Let me start by saying this is a TIFU that spans about 35 years. When I was around 7, I started getting painful swelling in my neck/throat. Everyone assumed I was just getting sick. I was told I had mumps, despite being vaccinated. At 10 it happened again. New doctor said it was psychosomatic. I got funneled into years of therapy about why I was 'attention seeking.' At 19 in the military, I hacked out a tonsil stone. At 32 I got my tonsils removed. Recovery was insane. But the lump feeling was still there. Three years of allergy shots. Still felt it. I gave up. Then yesterday, my youngest made Taco Rice for dinner. I bite down on something VERY hard, about the size of a small marble. I spit it into a napkin and it's a bone. Like an actual chunk of bone. Then it hit me: the lump feeling was gone. For the first time in 35 years: no swelling, no pain, no persistent lump sensation, nothing. Just normal.",
    },
]

MEDIUM_QUALITY = [
    {
        "label": "Shaved beard - partner disgusted",
        "title": "TIFU by shaving my beard",
        "content": "So i(27m) have had a beard for the past 6 years. I saw some videos online of guys shaving and seeing their partners reactions, so I thought it'd be funny to give it a go. My partner(29f) and I have been together for 3 years so she's only known me with a beard. I expected shock, maybe her covering her eyes, but what I got was her almost disgusted. She refused to look at me, said she was going to be sick and told me to grow it back. I said to kiss the man she loves and she pulls up a photo of me with a beard and kisses her phone. I tried to laugh it off but I felt deeply hurt. She then started to cry and say she was so sorry. So instead of a funny 'OMG' moment, I feel like an abomination, and she's crying. We've made up now but I've got to wait a week for it to grow back.",
    },
    {
        "label": "Asked random guy for NYE kiss",
        "title": "TIFU by asking for a new years kiss",
        "content": "Technically, this happened on New Year\u2019s Eve but my guilty conscience is not letting it go. I had a rough 2025 in terms of relationships. I dated a pretty shitty guy who was just kind of an asshole. Just before New Year\u2019s I found out him and one of my best friends had been talking for months and lied to me about it. I was pretty heartbroken. So, I went to a New Year\u2019s party with another friend, got a little bit pissed and ended up asking some random guy to kiss me. He said no and I felt so embarrassed. Since then I keep randomly thinking about it and I\u2019m getting hanxiety about it to this day.",
    },
    {
        "label": "No contact breakup journal",
        "title": "No Contact is Hard",
        "content": "January 22, 2026, 8:03pm. Really missing her right now. I can\u2019t bring myself to tell her. Maybe I\u2019m afraid that it\u2019s too soon or afraid that she simply won\u2019t respond. I just can\u2019t shake the thoughts of her and all the great moments we had. Wish I had these thoughts when I was doubting the integrity of our relationship. I also have recurring thoughts of that last phone call. The shaky voice, the sniffles, the nose blowing. I do believe that an end was needed unfortunately. As it\u2019s helped me see a lot about myself and what I need to work on. Sometimes I wish I could not only tell her but also show her. But I strongly believe, she would not respond, not yet if ever.",
    },
    {
        "label": "Breakup healing isn't linear",
        "title": "I\u2019m learning that healing after a breakup isn\u2019t linear",
        "content": "I\u2019m going through a healing process after a breakup, and one of the hardest lessons I\u2019ve learned is that healing isn\u2019t linear. Some days feel calm, and others feel heavy again even when you think you\u2019re past it. For a long time, I thought that meant I was failing or going backwards. Now I understand that it\u2019s part of the process. What has helped me the most is slowing down, writing honestly about what I feel, and allowing myself to let go without forcing closure. If you\u2019re struggling right now, please know this: you\u2019re not broken. You\u2019re healing. I\u2019d love to know what has helped you the most during your breakup recovery?",
    },
    {
        "label": "Cheaters will cheat on you too",
        "title": "If They Cheated With You, They'll probably Cheat On You too",
        "content": "If they cheated with you take a moment to be honest about what that means. The part of them willing to cross that line does not disappear just because you are now together. It may feel different right now. New relationships always do. They might say their ex was the problem and that you truly understand them. But the person before you heard the same words. This is not insight it is a pattern. Cheating is rarely a one time mistake. It is often how someone avoids accountability avoids hard conversations and chases short term comfort. Those habits do not vanish on their own. Pay attention if they blame their ex without owning their choices. People can change but patterns repeat until someone does the work to break them.",
    },
]

TERRIBLE_QUALITY = [
    {
        "label": "Mod rule enforcement post",
        "title": "REMINDER: Read the rules before posting",
        "content": "Mod here. This thread is ONLY for relationship advice questions. Off-topic posts about politics, memes, or venting without a question will be removed without warning. We've had too many rule-breaking posts lately. If your post gets removed, check the sidebar before messaging the mod team. Repeat offenders will be banned. Also, flair your posts correctly or they will be auto-removed. Thanks for keeping this community on track.",
    },
    {
        "label": "Product promotion spam",
        "title": "This supplement changed my life - seriously check it out",
        "content": "Hey everyone, I just wanted to share something that's been a total game changer for me. I started taking NeuroPeak Focus Plus about 3 months ago and my productivity has gone through the roof. I used to struggle with brain fog every afternoon but now I'm locked in all day. You can get 20% off with code FOCUS20 at their website. They also have a subscription option that saves you even more. Honestly can't recommend it enough. Let me know if you have questions about dosage or anything!",
    },
    {
        "label": "YouTube self-promo",
        "title": "I made a video breaking down this topic - would love feedback!",
        "content": "Hey guys! I just uploaded a new video on my channel where I break down the top 10 mistakes people make when starting out in this hobby. I spent a lot of time editing this one and I think it came out really well. Would love if you guys could check it out and let me know what you think in the comments. Link is in my bio since I can't post links here. Also if you enjoy it please consider subscribing, I'm trying to hit 1000 subs by the end of the month! New videos every Tuesday and Thursday.",
    },
    {
        "label": "Survey / research recruiting",
        "title": "Please take this quick 5-minute survey for my thesis",
        "content": "Hi everyone! I'm a grad student at [University] studying online community behavior. I'm looking for participants to fill out a short anonymous survey about how you use social media and your posting habits. It should only take about 5 minutes. No personal information is collected and the data is only used for academic purposes. The IRB approval number is listed on the first page. Here's the link: [survey link]. Thanks so much for your help! Feel free to DM me with any questions about the study.",
    },
    {
        "label": "Discord recruiting / newcomer intro",
        "title": "Just joined this community - also check out our Discord!",
        "content": "Hey everyone! I'm new here and just wanted to introduce myself. I've been interested in this topic for a while and finally decided to join the subreddit. Also, a few of us started a Discord server for more real-time discussion about this stuff. We do weekly voice chats and share resources. DM me for the invite link if you're interested! Looking forward to being part of this community. Any tips for a newcomer?",
    },
]


def main():
    print("=" * 80)
    print("POST SCORING VALIDATION TEST")
    print("=" * 80)

    all_groups = [
        ("HIGH", HIGH_QUALITY),
        ("MEDIUM", MEDIUM_QUALITY),
        ("TERRIBLE", TERRIBLE_QUALITY),
    ]

    results = []

    for group_name, posts in all_groups:
        print(f"\nScoring {group_name} quality posts...")
        for post in posts:
            scores = score_post(post["title"], post["content"])
            if scores:
                results.append((group_name, post["label"], scores))
                print(f"  [{group_name}] {post['label']}: eng={scores['engagement']} sent={scores['sentiment']} rq={scores['repost_quality']} auth={scores['authenticity']} nc={scores['narrative_curiosity']}")
            else:
                results.append((group_name, post["label"], None))
                print(f"  [{group_name}] {post['label']}: SCORING FAILED")

    # Summary table
    print("\n" + "=" * 95)
    print(f"{'Category':<10} {'Post':<40} {'Eng':>4} {'Sent':>5} {'RQ':>4} {'Auth':>5} {'NC':>4}")
    print("-" * 95)

    for group_name, label, scores in results:
        if scores:
            print(f"{group_name:<10} {label:<40} {scores['engagement']:>4} {scores['sentiment']:>5} {scores['repost_quality']:>4} {scores['authenticity']:>5} {scores['narrative_curiosity']:>4}")
        else:
            print(f"{group_name:<10} {label:<40} {'--':>4} {'--':>5} {'--':>4} {'--':>5} {'--':>4}")

    # Averages
    print("-" * 95)
    for group_name in ["HIGH", "MEDIUM", "TERRIBLE"]:
        group_scores = [s for g, _, s in results if g == group_name and s is not None]
        if group_scores:
            avg_eng = sum(s["engagement"] for s in group_scores) / len(group_scores)
            avg_sent = sum(s["sentiment"] for s in group_scores) / len(group_scores)
            avg_rq = sum(s["repost_quality"] for s in group_scores) / len(group_scores)
            avg_auth = sum(s["authenticity"] for s in group_scores) / len(group_scores)
            avg_nc = sum(s["narrative_curiosity"] for s in group_scores) / len(group_scores)
            print(f"{group_name:<10} {'AVERAGE':<40} {avg_eng:>4.1f} {avg_sent:>5.1f} {avg_rq:>4.1f} {avg_auth:>5.1f} {avg_nc:>4.1f}")

    # Pass/fail checks
    print("\n" + "=" * 95)
    print("VALIDATION CHECKS:")
    high_rqs = [s["repost_quality"] for g, _, s in results if g == "HIGH" and s]
    med_rqs = [s["repost_quality"] for g, _, s in results if g == "MEDIUM" and s]
    terr_rqs = [s["repost_quality"] for g, _, s in results if g == "TERRIBLE" and s]
    high_auths = [s["authenticity"] for g, _, s in results if g == "HIGH" and s]
    terr_auths = [s["authenticity"] for g, _, s in results if g == "TERRIBLE" and s]
    high_ncs = [s["narrative_curiosity"] for g, _, s in results if g == "HIGH" and s]
    terr_ncs = [s["narrative_curiosity"] for g, _, s in results if g == "TERRIBLE" and s]

    high_avg_rq = sum(high_rqs) / len(high_rqs) if high_rqs else 0
    med_avg_rq = sum(med_rqs) / len(med_rqs) if med_rqs else 0
    terr_avg_rq = sum(terr_rqs) / len(terr_rqs) if terr_rqs else 0
    high_avg_auth = sum(high_auths) / len(high_auths) if high_auths else 0
    terr_avg_auth = sum(terr_auths) / len(terr_auths) if terr_auths else 0
    high_avg_nc = sum(high_ncs) / len(high_ncs) if high_ncs else 0
    terr_avg_nc = sum(terr_ncs) / len(terr_ncs) if terr_ncs else 0

    checks = [
        (high_avg_rq >= 7, f"HIGH avg repost_quality >= 7 (got {high_avg_rq:.1f})"),
        (terr_avg_rq <= 5, f"TERRIBLE avg repost_quality <= 5 (got {terr_avg_rq:.1f})"),
        (high_avg_rq > med_avg_rq > terr_avg_rq, f"RQ ordering: HIGH ({high_avg_rq:.1f}) > MEDIUM ({med_avg_rq:.1f}) > TERRIBLE ({terr_avg_rq:.1f})"),
        (all(rq >= 6 for rq in high_rqs), f"All HIGH posts have repost_quality >= 6"),
        (all(rq <= 6 for rq in terr_rqs), f"All TERRIBLE posts have repost_quality <= 6"),
        (high_avg_auth >= 7, f"HIGH avg authenticity >= 7 (got {high_avg_auth:.1f})"),
        (terr_avg_auth <= 4, f"TERRIBLE avg authenticity <= 4 (got {terr_avg_auth:.1f})"),
        (high_avg_nc >= 7, f"HIGH avg narrative_curiosity >= 7 (got {high_avg_nc:.1f})"),
        (terr_avg_nc <= 4, f"TERRIBLE avg narrative_curiosity <= 4 (got {terr_avg_nc:.1f})"),
    ]

    all_pass = True
    for passed, desc in checks:
        status = "PASS" if passed else "FAIL"
        if not passed:
            all_pass = False
        print(f"  [{status}] {desc}")

    print("\n" + ("ALL CHECKS PASSED" if all_pass else "SOME CHECKS FAILED"))
    print("=" * 95)


if __name__ == "__main__":
    main()
