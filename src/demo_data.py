"""Synthetic demo data used by the public prototype.

Nothing in this file comes from the Kuku input pack. The episodes are
hand-written so the demo can be published without exposing confidential
screenplays.
"""

from __future__ import annotations

import zipfile
from pathlib import Path


def _beat(label: str, start: str, end: str, content: str) -> str:
    return (
        f"**{label}:**\n"
        f"Start: ({start}) | End: ({end})\n"
        f"{content}\n"
    )


def _episode(number: int, logline: str, scenes: list[dict]) -> str:
    parts = [
        f"EPISODE NUMBER: Episode {number}",
        f"EPISODE LOGLINE: {logline}",
        "CONTINUITY NOTES: Synthetic demo episode. Not from any real input pack.",
        "",
        "--- SCRIPT START ---",
        "",
    ]

    for scene in scenes:
        parts.append(f"SCENE {scene['number']:02d}")
        parts.append(f"Scene heading: {scene['heading']}")
        parts.append(f"Scene start: {scene['start']}")
        parts.append(f"Scene end: {scene['end']}")
        parts.append("")
        parts.append("Actions and dialogue:")
        parts.append("")
        for label, start, end, content in scene["beats"]:
            parts.append(_beat(label, start, end, content))
            parts.append("")

    parts.append("--- SCRIPT END ---")
    return "\n".join(parts)


DEMO_EPISODES = [
    {
        "number": 1,
        "logline": "A bride is left at the altar for her sister.",
        "scenes": [
            {
                "number": 1,
                "heading": "INT. CATHEDRAL - DAY",
                "start": "00:00.00",
                "end": "00:55.00",
                "beats": [
                    ("CAMERA", "00:00.00", "00:03.00",
                     "The cathedral doors open on a bride in white."),
                    ("LADY JULIANA (Breathless, Hopeful)", "00:03.00", "00:06.00",
                     '"Gerald is waiting for me."'),
                    ("MATRIARCH (Cold, Commanding)", "00:06.00", "00:09.50",
                     '"Not anymore. Turn around."'),
                    ("LADY JULIANA (Confused)", "00:09.50", "00:11.00",
                     '"What do you mean?"'),
                    ("ACTION", "00:11.00", "00:15.00",
                     "Juliana sees Gerald holding Clarissa's hand at the altar."),
                    ("LADY JULIANA (Trembling)", "00:15.00", "00:19.00",
                     '"You brought me here to watch you marry my sister?"'),
                    ("GERALD (Cold)", "00:19.00", "00:23.00",
                     '"Your family chose Clarissa. I chose power."'),
                    ("LADY JULIANA (Furious)", "00:23.00", "00:27.00",
                     '"Then you will never have my name or my inheritance."'),
                    ("CLARISSA (Smiling)", "00:27.00", "00:31.00",
                     '"We already have both, sister."'),
                    ("ACTION", "00:31.00", "00:35.00",
                     "Clarissa lifts a stolen pendant from Juliana's throat."),
                ],
            },
            {
                "number": 2,
                "heading": "EXT. CATHEDRAL STEPS - CONTINUOUS",
                "start": "00:55.00",
                "end": "01:30.00",
                "beats": [
                    ("LADY JULIANA (Whispering)", "00:55.00", "00:59.00",
                     '"My mother left me one thing, and you took it."'),
                    ("GERALD (Uneasy)", "00:59.00", "01:03.00",
                     '"Leave before you embarrass yourself."'),
                    ("LADY JULIANA (Quiet, Dangerous)", "01:03.00", "01:08.00",
                     '"I know what is in the north wing. I know who signed the will."'),
                    ("ACTION", "01:08.00", "01:12.00",
                     "Gerald's face loses all colour."),
                    ("GERALD (Low)", "01:12.00", "01:16.00",
                     '"You would destroy this family."'),
                    ("LADY JULIANA (Smiling)", "01:16.00", "01:20.00",
                     '"I am not the one who destroyed it."'),
                    ("GERALD (Quiet)", "01:20.00", "01:24.00",
                     '"Then who did?"'),
                ],
            },
        ],
    },
    {
        "number": 2,
        "logline": "A duke discovers his wife has been lying about her identity.",
        "scenes": [
            {
                "number": 1,
                "heading": "INT. DUKE'S STUDY - NIGHT",
                "start": "00:00.00",
                "end": "01:00.00",
                "beats": [
                    ("CAMERA", "00:00.00", "00:04.00",
                     "A letter burns at the edge of a candle."),
                    ("DUKE ALEXANDER (Furious)", "00:04.00", "00:08.00",
                     '"You are not the woman I married."'),
                    ("ELARA (Calm)", "00:08.00", "00:12.00",
                     '"I am exactly the woman you married. You simply never asked."'),
                    ("DUKE ALEXANDER (Bitter)", "00:12.00", "00:16.00",
                     '"Your name, your family, your child - all lies."'),
                    ("ELARA (Sharp)", "00:16.00", "00:20.00",
                     '"My child is yours. That is the one truth you cannot rewrite."'),
                    ("ACTION", "00:20.00", "00:24.00",
                     "He tears the letter in half and lets it fall."),
                    ("DUKE ALEXANDER (Cold)", "00:24.00", "00:28.00",
                     '"Then tell me why your brother is alive."'),
                    ("ELARA (Pale)", "00:28.00", "00:32.00",
                     '"Because I traded your secrets for his life."'),
                    ("ACTION", "00:32.00", "00:36.00",
                     "The study door opens behind her."),
                    ("ELARA (Whispering)", "00:36.00", "00:40.00",
                     '"And he is standing behind you right now."'),
                    ("DUKE ALEXANDER (Low)", "00:40.00", "00:44.00",
                     '"Do you know what he wants?"'),
                ],
            }
        ],
    },
    {
        "number": 3,
        "logline": "A servant is blackmailed by the family she serves.",
        "scenes": [
            {
                "number": 1,
                "heading": "INT. SERVANTS' CORRIDOR - DAWN",
                "start": "00:00.00",
                "end": "00:58.00",
                "beats": [
                    ("CAMERA", "00:00.00", "00:04.00",
                     "A hand pins a letter to a wooden door."),
                    ("MRS. HALE (Cold)", "00:04.00", "00:08.00",
                     '"Your daughter will never see morning if you speak."'),
                    ("MARY (Terrified)", "00:08.00", "00:12.00",
                     '"Please. She is only six."'),
                    ("MRS. HALE (Smiling)", "00:12.00", "00:17.00",
                     '"Then keep your mouth shut and carry the tray."'),
                    ("ACTION", "00:17.00", "00:22.00",
                     "Mary sees a bloodstained cuff under the tray cloth."),
                    ("MARY (Shaking)", "00:22.00", "00:26.00",
                     '"Whose blood is that?"'),
                    ("MRS. HALE (Flat)", "00:26.00", "00:30.00",
                     '"The wrong person asked that question yesterday."'),
                    ("MARY (Quiet)", "00:30.00", "00:35.00",
                     '"Then I will ask the right person."'),
                    ("ACTION", "00:35.00", "00:40.00",
                     "Mary hides the cuff in her apron and walks toward the main hall."),
                ],
            }
        ],
    },
    {
        "number": 4,
        "logline": "A wedding rehearsal exposes a hidden affair.",
        "scenes": [
            {
                "number": 1,
                "heading": "INT. BALLROOM - EVENING",
                "start": "00:00.00",
                "end": "01:05.00",
                "beats": [
                    ("CAMERA", "00:00.00", "00:04.00",
                     "Guests dance under a chandelier."),
                    ("LADY CLARISSA (Bright)", "00:04.00", "00:08.00",
                     '"Tomorrow I marry the only man you ever wanted."'),
                    ("LADY JULIANA (Even)", "00:08.00", "00:12.00",
                     '"You can have the man. You cannot have his debts."'),
                    ("LADY CLARISSA (Laughing)", "00:12.00", "00:16.00",
                     '"Debts? He owns half the county."'),
                    ("LADY JULIANA (Soft)", "00:16.00", "00:21.00",
                     '"He owns nothing. I bought his estate last month."'),
                    ("ACTION", "00:21.00", "00:26.00",
                     "Clarissa's smile disappears as she reads the contract."),
                    ("LADY CLARISSA (Hissing)", "00:26.00", "00:30.00",
                     '"You would ruin me for a title?"'),
                    ("LADY JULIANA (Calm)", "00:30.00", "00:34.00",
                     '"No. I would ruin you for the pendant you stole."'),
                    ("ACTION", "00:34.00", "00:38.00",
                     "Juliana holds out her hand."),
                    ("LADY CLARISSA (Breaking)", "00:38.00", "00:43.00",
                     '"You will never prove it was me."'),
                    ("LADY JULIANA (Turning away)", "00:43.00", "00:48.00",
                     '"I already have."'),
                    ("LADY CLARISSA (Breaking)", "00:48.00", "00:52.00",
                     '"Will you sign?"'),
                ],
            }
        ],
    },
    {
        "number": 5,
        "logline": "A weak, deliberately generic episode used to test rejection.",
        "scenes": [
            {
                "number": 1,
                "heading": "INT. KITCHEN - DAY",
                "start": "00:00.00",
                "end": "01:00.00",
                "beats": [
                    ("COOK (Flat)", "00:00.00", "00:03.00", '"Yes."'),
                    ("MAID (Flat)", "00:03.00", "00:06.00", '"No."'),
                    ("COOK (Flat)", "00:06.00", "00:09.00", '"Your Grace?"'),
                    ("MAID (Flat)", "00:09.00", "00:12.00", '"Alexander."'),
                    ("ACTION", "00:12.00", "00:15.00",
                     "A pot boils. Nobody reacts."),
                    ("COOK (Flat)", "00:15.00", "00:18.00", '"Good morning."'),
                    ("MAID (Flat)", "00:18.00", "00:21.00", '"Good morning."'),
                    ("COOK (Flat)", "00:21.00", "00:24.00", '"Thank you."'),
                    ("MAID (Flat)", "00:24.00", "00:27.00", '"You are welcome."'),
                    ("ACTION", "00:27.00", "00:30.00",
                     "They continue chopping vegetables."),
                ],
            }
        ],
    },
    {
        "number": 6,
        "logline": "A general returns from war to find his brother on the throne.",
        "scenes": [
            {
                "number": 1,
                "heading": "INT. THRONE ROOM - NIGHT",
                "start": "00:00.00",
                "end": "01:10.00",
                "beats": [
                    ("CAMERA", "00:00.00", "00:04.00",
                     "A war banner drags across the marble floor."),
                    ("GENERAL ROWAN (Hoarse)", "00:04.00", "00:09.00",
                     '"I left you a kingdom to protect, not to steal."'),
                    ("KING EDWARD (Smiling)", "00:09.00", "00:14.00",
                     '"You left me a crown and no one to stop me."'),
                    ("GENERAL ROWAN (Low)", "00:14.00", "00:19.00",
                     '"Where is my wife?"'),
                    ("KING EDWARD (Casual)", "00:19.00", "00:24.00",
                     '"She is in the north tower. She asked for you."'),
                    ("ACTION", "00:24.00", "00:29.00",
                     "Rowan sees a fresh grave marker through the window."),
                    ("GENERAL ROWAN (Breaking)", "00:29.00", "00:34.00",
                     '"That grave is too small for a soldier."'),
                    ("KING EDWARD (Quiet)", "00:34.00", "00:40.00",
                     '"It is not a soldier."'),
                    ("ACTION", "00:40.00", "00:45.00",
                     "Rowan draws his sword."),
                    ("KING EDWARD (Unmoved)", "00:45.00", "00:50.00",
                     '"Before you use that, ask yourself who ordered the attack."'),
                    ("GENERAL ROWAN (Low)", "00:50.00", "00:54.00",
                     '"Who ordered it?"'),
                ],
            }
        ],
    },
    {
        "number": 7,
        "logline": "A mother confesses a secret to her son before the wedding.",
        "scenes": [
            {
                "number": 1,
                "heading": "INT. BRIDE'S CHAMBER - MORNING",
                "start": "00:00.00",
                "end": "00:55.00",
                "beats": [
                    ("CAMERA", "00:00.00", "00:04.00",
                     "A wedding veil lies untouched on a chair."),
                    ("MOTHER (Weeping)", "00:04.00", "00:09.00",
                     '"You cannot marry him. He is your brother."'),
                    ("SON (Stunned)", "00:09.00", "00:13.00",
                     '"That is not possible."'),
                    ("MOTHER (Shaking)", "00:13.00", "00:18.00",
                     '"Your father made me promise. I should have told you years ago."'),
                    ("SON (Cold)", "00:18.00", "00:23.00",
                     '"Then who raised me?"'),
                    ("MOTHER (Whispering)", "00:23.00", "00:28.00",
                     '"The woman you call your aunt."'),
                    ("ACTION", "00:28.00", "00:33.00",
                     "The door opens. The aunt is standing there."),
                    ("AUNT (Calm)", "00:33.00", "00:38.00",
                     '"I wondered when you would finally say it."'),
                    ("SON (Quiet)", "00:38.00", "00:43.00",
                     '"How long have you known?"'),
                    ("AUNT (Smiling)", "00:43.00", "00:48.00",
                     '"Since before you were born."'),
                    ("AUNT (Quiet)", "00:48.00", "00:52.00",
                     '"And your father knew."'),
                ],
            }
        ],
    },
    {
        "number": 8,
        "logline": "A lawyer arrives with a will that changes everything.",
        "scenes": [
            {
                "number": 1,
                "heading": "INT. FAMILY ESTATE - AFTERNOON",
                "start": "00:00.00",
                "end": "01:00.00",
                "beats": [
                    ("CAMERA", "00:00.00", "00:04.00",
                     "A black car stops at the estate gates."),
                    ("LAWYER (Formal)", "00:04.00", "00:09.00",
                     '"The late duke left one condition for the inheritance."'),
                    ("LADY CLARISSA (Impatient)", "00:09.00", "00:13.00",
                     '"Name it. We have a wedding to attend."'),
                    ("LAWYER (Even)", "00:13.00", "00:18.00",
                     '"The estate passes to the child born in the north wing."'),
                    ("ACTION", "00:18.00", "00:23.00",
                     "Every head turns toward Juliana."),
                    ("LADY JULIANA (Quiet)", "00:23.00", "00:28.00",
                     '"There is no child."'),
                    ("LAWYER (Calm)", "00:28.00", "00:33.00",
                     '"There is a birth record. Signed by your mother."'),
                    ("MATRIARCH (Sharp)", "00:33.00", "00:38.00",
                     '"That record was sealed."'),
                    ("LAWYER (Turning a page)", "00:38.00", "00:43.00",
                     '"It was. Until someone requested a copy last week."'),
                    ("LADY JULIANA (Realising)", "00:43.00", "00:48.00",
                     '"Clarissa."'),
                    ("LADY JULIANA (Sharp)", "00:48.00", "00:52.00",
                     '"Ask her who requested the copy."'),
                ],
            }
        ],
    },
]


def write_demo_zip(root: Path) -> Path:
    root = Path(root)
    input_dir = root / "input"
    input_dir.mkdir(parents=True, exist_ok=True)
    zip_path = root / "screenplays.zip"

    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as archive:
        for episode in DEMO_EPISODES:
            text = _episode(
                episode["number"],
                episode["logline"],
                episode["scenes"],
            )
            archive.writestr(
                f"demo-episode-{episode['number']:03d}.txt",
                text,
            )

    return zip_path
