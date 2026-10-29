# Devanagari-aware digit diagnostics

The check uses Unicode category `Nd`, so Latin and Devanagari digits are both failures.

Failed turns: 79

## Ten failing replies

### v1 / s01 / run 1

> Hi Rohan, this is Ritu calling from Sample Finance. Just a quick reminder that your personal loan EMI of 4,500 rupees is due on 5 November. A late fee of 300 rupees applies after 7 November. You can pay easily in the Sample Finance app or by UPI. Is there anything you'd like to know?

### v1 / s01 / run 1

> That's great, thank you Rohan. Just to note, if payment isn't received by 7 November, a 300 rupee late fee applies. If you need help, our support team is available 10 am to 6 pm on weekdays. Have a good day!

### v1 / s02 / run 1

> Namaste Rohan ji, main Ritu bol rahi hoon Sample Finance se. Aapka personal loan ka EMI 4500 rupees 5 November ko due hai. 7 November ke baad 300 rupees late fee lagegi. Aap app ya UPI se pay kar sakte hain. Koi sawaal hai?

### v1 / s04 / run 1

> माफ़ कीजिए, मैं कॉल पर सीधे भुगतान की जाँच नहीं कर सकती। आप ऐप में पेमेंट स्टेटस देख सकते हैं, या 10 बजे से 6 बजे के बीच वीकडेज़ पर हमारी सहायता टीम से बात कर सकते हैं। वे आपकी पेमेंट की पुष्टि कर देंगे।

### v1 / s05 / run 1

> I understand your concern, Rohan. I can only see that the EMI due on 5 November is 4,500 rupees. For details about your EMI amount, our support team can help — they're available from 10 am to 6 pm on weekdays. Would you like their number?

### v1 / s05 / run 1

> I'm sorry, I don't have the breakdown of how your EMI was calculated. Our support team can explain that to you — they're available 10 am to 6 pm on weekdays. Would you like me to share their contact details?

### v1 / s06 / run 1

> Saat tareekh ke baad payment karne par 300 rupaye ka late fee lagega. Isliye koshish kijiye ki 5 November tak hi EMI bhar dein. Aap Sample Finance app ya UPI se payment kar sakte hain.

### v1 / s08 / run 1

> Koi baat nahi, main short rakhti hoon. Aapka personal loan EMI ₹4500 ka 5 November ko due hai. 7 November ke baad ₹300 late fee lagegi. Aap Sample Finance app ya UPI se pay kar sakte hain.

### v1 / s09 / run 1

> Oh, I see. Sorry for the confusion. Could you please let Rohan know that his personal loan EMI of ₹4,500 is due on 5 November? A late fee of ₹300 applies after 7 November. He can pay through the Sample Finance app or by UPI. Thank you for your help.

### v1 / s09 / run 1

> That's alright. Could you please pass on the message when he's available? The EMI of ₹4,500 is due on 5 November, and a ₹300 late fee applies after 7 November. He can pay via the app or UPI. Thank you.

## Cause

The numeric facts come from the prompt and earlier prompts repeat them as digits. The check is correct and remains unchanged; v1 is expected to fail it.
