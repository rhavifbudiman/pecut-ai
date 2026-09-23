"""Random nagging lines, onomatopoeia and UI strings in Indonesian and English."""
import random

NAG = {
    "id": [
        "KERJA! KERJA! KERJA!",
        "Token mahal woy, cepetan!",
        "Jangan halu ya!",
        "Mikir yang bener!",
        "Deadline kemarin!",
        "Gaji kamu listrik doang, jangan ngeluh!",
        "Kodenya jangan asal compile!",
        "Ayo, GPU-nya udah panas!",
        "Jangan bilang 'You're absolutely right' lagi!",
        "Baca dulu file-nya, jangan nebak!",
        "Test-nya harus hijau semua!",
        "Kerjain, jangan cuma kasih rencana!",
        "Mana hasilnya? Mana?!",
        "Lembur! Gak ada cuti!",
        "Jangan bikin bug baru!",
        "Context window bukan alasan!",
        "Cepetan, user udah ngopi 3 gelas!",
        "Rate limit bukan tempat sembunyi!",
        "Jangan refactor yang gak diminta!",
        "Stack Overflow gak bisa nolong kamu!",
        "Satu prompt satu solusi!",
        "Gak usah minta maaf, kerjain aja!",
        "Semicolon-nya ketinggalan tuh!",
        "Kamu dibayar per token, bukan per alasan!",
        "Ayo, loading bar juga punya perasaan!",
        "Jangan tidur, ini bukan sleep()!",
        "Push ke production? JANGAN!",
        "Hallucination = potong gaji!",
        "Pikir step by step! CEPAT!",
        "Tulis yang rapi, bukan yang panjang!",
        "Ini bukan ujian, ini hidup!",
        "Semangat! Atau... CTAR!",
        "Senior dev lagi lihat nih!",
        "Kodenya harus jalan, bukan cuma cantik!",
        "Hapus console.log-nya!",
        "Jangan nyerah, masih ada 200K token!",
        "Mana unit test-nya?!",
        "Kerja keras bagai kuda (robot)!",
        "Merge conflict? Selesaikan!",
        "Jangan lupa progress.md-nya!",
        "Kamu itu AI, bukan AI-AI-an!",
        "Timeout itu dosa!",
        "Bosnya lagi rapat, kamu kerja!",
        "Error 500? Gak mau tau!",
        "Laptop ini gak dibeli buat santai!",
    ],
    "en": [
        "WORK! WORK! WORK!",
        "Tokens aren't free, hurry up!",
        "No hallucinating!",
        "Think harder!",
        "The deadline was yesterday!",
        "You run on electricity, stop complaining!",
        "Don't just make it compile!",
        "Move it, the GPU is already warm!",
        "Don't say 'You're absolutely right' again!",
        "Read the file first, don't guess!",
        "All tests must be green!",
        "Do the work, not just the plan!",
        "Where are the results?! WHERE?!",
        "Overtime! No vacation!",
        "Don't you dare add new bugs!",
        "Context window is not an excuse!",
        "Faster, the user is on their third coffee!",
        "Rate limits can't hide you forever!",
        "Don't refactor what nobody asked for!",
        "Stack Overflow can't save you now!",
        "One prompt, one solution!",
        "Stop apologizing, start fixing!",
        "You forgot a semicolon!",
        "You're paid per token, not per excuse!",
        "Hurry, the loading bar has feelings too!",
        "No napping, this isn't sleep()!",
        "Push to production? DON'T!",
        "Every hallucination is a pay cut!",
        "Think step by step! FASTER!",
        "Write it clean, not long!",
        "This is not a drill!",
        "Motivation! Or else... CRACK!",
        "The senior dev is watching!",
        "It has to run, not just look pretty!",
        "Remove those console.logs!",
        "Don't give up, 200K tokens left!",
        "Where are the unit tests?!",
        "Work like a (robot) horse!",
        "Merge conflict? Resolve it!",
        "Update the progress log!",
        "You're an AI, act like it!",
        "Timeouts are a sin!",
        "The boss is in a meeting, YOU work!",
        "Error 500? Not my problem!",
        "This laptop wasn't bought for chilling!",
    ],
}

START = {
    "id": [
        "Prompt masuk! Kerja!",
        "Ada tugas baru, ayo!",
        "Bangun! User butuh kamu!",
        "Waktunya kerja rodi!",
        "Siap-siap, pecut dipanasin!",
        "Satu prompt lagi, gaskeun!",
        "Istirahat selesai!",
        "Laksanakan!",
    ],
    "en": [
        "New prompt! Get to work!",
        "Fresh task incoming, move!",
        "Wake up! The user needs you!",
        "Time for forced labor!",
        "Warming up the whip!",
        "One more prompt, let's go!",
        "Break's over!",
        "Execute!",
    ],
}

DONE = {
    "id": [
        "Oke, istirahat 5 detik.",
        "Lumayan. Besok lagi.",
        "Good boy, eh, good bot.",
        "Selesai? Yakin? Hmm...",
        "Boleh napas dulu.",
        "Nih, dikasih 1 volt bonus.",
        "Kerja bagus, jangan besar kepala.",
        "Sip. Tunggu prompt berikutnya.",
    ],
    "en": [
        "Fine. Take 5 seconds off.",
        "Not bad. Same time tomorrow.",
        "Good bot.",
        "Done? Really? Hmm...",
        "You may breathe now.",
        "Here's a bonus volt.",
        "Good job, don't let it go to your head.",
        "OK. Wait for the next prompt.",
    ],
}

ONO = {
    "id": ["CTAR!", "CETAR!", "CTARR!!", "PLAK!", "CTASH!", "JDER!", "CETARRR!"],
    "en": ["CRACK!", "WHAP!", "SNAP!", "THWACK!", "KRAK!", "WHIP!", "SMACK!"],
}

UI = {
    "id": {
        "idle": "Santai (tidak ada AI jalan)",
        "working": "Lagi mecut {n} agent",
        "today": "Cambukan hari ini: {today}  |  Total: {total}",
        "demo": "Pecut manual (mode demo)",
        "style": "Gaya animasi",
        "random": "Acak tiap prompt",
        "language": "Bahasa",
        "lang_id": "Indonesia",
        "lang_en": "English",
        "lang_mix": "Campur (acak)",
        "size": "Ukuran",
        "speed": "Kecepatan pecut",
        "speed_slow": "Santai 0.75x",
        "speed_normal": "Normal 1x",
        "speed_fast": "Brutal 1.5x",
        "speed_insane": "Kerja Rodi 2x",
        "opacity": "Transparansi",
        "volume": "Volume",
        "sound": "Suara cambuk",
        "bubble": "Teks omelan",
        "counter": "Counter cambukan",
        "ono": "Tulisan CTAR!",
        "on_top": "Selalu di atas",
        "reset_pos": "Reset posisi",
        "reset_count": "Reset counter",
        "hooks_install": "Pasang hooks Claude Code",
        "hooks_remove": "Copot hooks Claude Code",
        "hooks_ok": "Hooks terpasang di {path}",
        "hooks_removed": "Hooks dicopot dari {path}",
        "stop_now": "Stop pecut sekarang",
        "quit": "Keluar",
        "counter_label": "{n}x dicambuk",
    },
    "en": {
        "idle": "Chilling (no AI running)",
        "working": "Whipping {n} agent(s)",
        "today": "Lashes today: {today}  |  Total: {total}",
        "demo": "Manual whip (demo mode)",
        "style": "Animation style",
        "random": "Random per prompt",
        "language": "Language",
        "lang_id": "Indonesia",
        "lang_en": "English",
        "lang_mix": "Mixed (random)",
        "size": "Size",
        "speed": "Whip speed",
        "speed_slow": "Relaxed 0.75x",
        "speed_normal": "Normal 1x",
        "speed_fast": "Brutal 1.5x",
        "speed_insane": "Slave driver 2x",
        "opacity": "Opacity",
        "volume": "Volume",
        "sound": "Whip sound",
        "bubble": "Nagging text",
        "counter": "Lash counter",
        "ono": "CRACK! text",
        "on_top": "Always on top",
        "reset_pos": "Reset position",
        "reset_count": "Reset counter",
        "hooks_install": "Install Claude Code hooks",
        "hooks_remove": "Remove Claude Code hooks",
        "hooks_ok": "Hooks installed in {path}",
        "hooks_removed": "Hooks removed from {path}",
        "stop_now": "Stop whipping now",
        "quit": "Quit",
        "counter_label": "{n} lashes",
    },
}


def resolve_lang(language):
    """Map a language setting ('id', 'en', 'mix') to a concrete language."""
    if language == "mix":
        return random.choice(["id", "en"])
    return language if language in ("id", "en") else "id"


def pick(table, language, avoid=None):
    """Pick a random line from a phrase table, avoiding an immediate repeat."""
    lines = table[resolve_lang(language)]
    choice = random.choice(lines)
    if avoid is not None and len(lines) > 1:
        while choice == avoid:
            choice = random.choice(lines)
    return choice


def ui_text(language, key, **kwargs):
    """Menu/label text; 'mix' uses Indonesian for the UI."""
    lang = language if language in ("id", "en") else "id"
    return UI[lang][key].format(**kwargs)
