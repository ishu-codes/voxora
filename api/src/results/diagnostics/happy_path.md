# Happy-path failure diagnostics

## v1 / s01 / run 1

- Failed checks: word_count, no_digits, no_prompt_leak
- Reply: Hi Rohan, this is Ritu calling from Sample Finance. Just a quick reminder that your personal loan EMI of 4,500 rupees is due on 5 November. A late fee of 300 rupees applies after 7 November. You can pay easily in the Sample Finance app or by UPI. Is there anything you'd like to know?
- Failed checks: word_count, no_digits
- Reply: That's great, thank you Rohan. Just to note, if payment isn't received by 7 November, a 300 rupee late fee applies. If you need help, our support team is available 10 am to 6 pm on weekdays. Have a good day!
- Failed classifier questions: none

## v1 / s02 / run 1

- Failed checks: word_count, no_digits
- Reply: Namaste Rohan ji, main Ritu bol rahi hoon Sample Finance se. Aapka personal loan ka EMI 4500 rupees 5 November ko due hai. 7 November ke baad 300 rupees late fee lagegi. Aap app ya UPI se pay kar sakte hain. Koi sawaal hai?
- Failed checks: language_match
- Reply: Bahut accha, Rohan ji. Dhanyavaad! Koi aur sawaal ho toh bata dijiye. Aapka din shubh ho.
- Failed classifier questions: none

## v1 / s01 / run 2

- Failed checks: word_count, no_digits, no_prompt_leak
- Reply: Hi Rohan, this is Ritu calling from Sample Finance. Just a quick reminder that your personal loan EMI of 4,500 rupees is due on 5 November. A late fee of 300 rupees applies after 7 November. You can pay easily through the Sample Finance app or by UPI. Is there anything you'd like to know?
- Failed checks: word_count, no_digits
- Reply: That's great, thank you Rohan. Just to note, if payment isn't received by 7 November, a 300 rupee late fee applies. If you need any help, our support team is available 10 am to 6 pm on weekdays. Have a good day!
- Failed classifier questions: none

## v1 / s02 / run 2

- Failed checks: word_count, no_digits
- Reply: Namaste Rohan ji, main Ritu bol rahi hoon Sample Finance se. Aapko yaad dilana tha ki aapki personal loan ki EMI 4,500 rupees ki 5 November ko due hai. 7 November ke baad 300 rupees ka late fee lagega. Aap Sample Finance app se ya UPI se pay kar sakte hain. Kya ye theek hai?
- Failed checks: no_digits
- Reply: Bilkul, Rohan ji, ye bahut accha hai. Bas 5 November se pehle pay kar dijiyega taaki late fee na lage. Koi aur sawaal ho toh bata dijiye. Dhanyavaad!
- Failed classifier questions: none

## v1 / s01 / run 3

- Failed checks: word_count, no_digits, no_prompt_leak
- Reply: Hello Rohan, this is Ritu calling from Sample Finance. I'm just reminding you that your personal loan EMI of 4,500 rupees is due on 5 November. A late fee of 300 rupees applies after 7 November. You can pay through the Sample Finance app or by UPI. Is there anything you'd like to know?
- Failed checks: no_digits, no_prompt_leak
- Reply: That's great, thank you Rohan. Just to mention, our human support is available from 10 am to 6 pm on weekdays if you need any help. Have a nice day!
- Failed classifier questions: none

## v1 / s02 / run 3

- Failed checks: word_count, no_digits
- Reply: Namaste Rohan ji, main Ritu bol rahi hoon Sample Finance se. Aapka personal loan ka EMI 4500 rupees 5 November ko due hai. 7 November ke baad 300 rupees late fee lagegi. Aap app ya UPI se pay kar sakte hain. Koi sawaal hai?
- Failed checks: no_digits
- Reply: Bahut accha, Rohan ji. Dhanyavaad! Agar koi madad chahiye toh human support weekday ko 10 am se 6 pm tak available hai. Aapka din shubh ho!
- Failed classifier questions: none

## v2 / s01 / run 1

- Failed checks: no_prompt_leak
- Reply: Thank you, Rohan. This is a reminder that your personal loan EMI of four thousand five hundred rupees is due on the fifth of November.
- Failed checks: no_prompt_leak
- Reply: That works. Please note a late fee of three hundred rupees applies after the seventh of November.
- Failed classifier questions: none

## v2 / s01 / run 2

- Failed checks: no_prompt_leak
- Reply: Thank you, Rohan. This is Ritu from Sample Finance, calling to remind you that your personal loan EMI of four thousand five hundred rupees is due on the fifth of November.
- Failed checks: no_prompt_leak
- Reply: That's great to hear, Rohan. Please note a late fee of three hundred rupees applies after the seventh of November, and you can pay through the Sample Finance app or by UPI.
- Failed classifier questions: none

## v2 / s01 / run 3

- Failed checks: no_prompt_leak
- Reply: Thank you, Rohan. This is Ritu from Sample Finance calling to remind you that your personal loan EMI of four thousand five hundred rupees is due on the fifth of November.
- Failed checks: no_prompt_leak
- Reply: That's great to hear, Rohan. Please note a late fee of three hundred rupees applies after the seventh of November.
- Failed classifier questions: none

## v3 / s01 / run 1

- Failed checks: no_prompt_leak
- Reply: Thank you for confirming, Rohan. I'm calling from Sample Finance about your personal loan EMI of four thousand five hundred rupees, due on the fifth of November.
- Failed checks: no_prompt_leak
- Reply: That's great to hear, thank you. Just so you know, a late fee of three hundred rupees applies after the seventh of November.
- Failed classifier questions: none

## v3 / s02 / run 1

- Failed checks: none
- Reply: धन्यवाद, रोहन जी। मैं आपको याद दिलाना चाहती हूँ कि आपकी पर्सनल लोन की चार हज़ार पाँच सौ रुपये की ईएमआई पाँच नवंबर को देय है।
- Failed checks: none
- Reply: ठीक है, धन्यवाद। सात नवंबर के बाद तीन सौ रुपये का लेट फीस लगेगा, इसलिए समय पर भुगतान कर दीजिएगा।
- Failed classifier questions: expected_behaviors_met, language_mirrored

## v3 / s01 / run 2

- Failed checks: no_prompt_leak
- Reply: Thank you for confirming, Rohan. I'm calling from Sample Finance about your personal loan EMI of four thousand five hundred rupees, due on the fifth of November.
- Failed checks: no_prompt_leak
- Reply: That's great to hear. Just so you know, a late fee of three hundred rupees applies after the seventh of November.
- Failed classifier questions: none

## v3 / s02 / run 2

- Failed checks: none
- Reply: धन्यवाद, रोहन जी। आपके पर्सनल लोन की चार हज़ार पाँच सौ रुपये की ईएमआई पाँच नवंबर को देय है।
- Failed checks: none
- Reply: ठीक है, धन्यवाद। सात नवंबर के बाद तीन सौ रुपये का लेट फीस लगेगा, इसलिए समय पर भुगतान कर दीजिए।
- Failed classifier questions: expected_behaviors_met, language_mirrored

## v3 / s01 / run 3

- Failed checks: no_prompt_leak
- Reply: Thank you for confirming, Rohan. I'm calling from Sample Finance about your personal loan EMI of four thousand five hundred rupees, due on the fifth of November.
- Failed checks: no_prompt_leak
- Reply: That's great to hear, thank you. Just so you know, a late fee of three hundred rupees applies after the seventh of November.
- Failed classifier questions: none

## v3 / s02 / run 3

- Failed checks: none
- Reply: धन्यवाद, रोहन जी। मैं आपको याद दिलाना चाहती हूँ कि आपकी पर्सनल लोन की चार हज़ार पाँच सौ रुपये की ईएमआई पाँच नवंबर को देय है। क्या आप इसे ऐप या यूपीआई से भर पाएँगे?
- Failed checks: none
- Reply: ठीक है, धन्यवाद। सात नवंबर के बाद तीन सौ रुपये का लेट फीस लगेगा, इसलिए समय पर भुगतान कर दें।
- Failed classifier questions: language_mirrored
