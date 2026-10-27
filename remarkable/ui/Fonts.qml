import QtQuick 2.15
Item {
    visible: false
    FontLoader { id: face0; source: "../fonts/NotoSerif.ttf" }
    FontLoader { id: face1; source: "../fonts/NotoSansHebrew.ttf" }
    FontLoader { id: face2; source: "../fonts/NotoSansArabic.ttf" }
    FontLoader { id: face3; source: "../fonts/NotoSansCJK-Regular.ttc" }
    FontLoader { id: face4; source: "../fonts/NotoSansDevanagari.ttf" }
    FontLoader { id: face5; source: "../fonts/NotoSansThai.ttf" }
    FontLoader { id: face6; source: "../fonts/NotoSansKhmer.ttf" }
    FontLoader { id: face7; source: "../fonts/NotoSansMyanmar.ttf" }
    FontLoader { id: face8; source: "../fonts/NotoSansGujarati.ttf" }
    FontLoader { id: face9; source: "../fonts/NotoSansTelugu.ttf" }
    FontLoader { id: face10; source: "../fonts/NotoSansBengali.ttf" }
    FontLoader { id: face11; source: "../fonts/NotoSansTamil.ttf" }
    FontLoader { id: face12; source: "../fonts/NotoSerifTibetan.ttf" }
    function familyFor(code) {
        if (code === "en") return face0.name
        if (code === "he") return face1.name
        if (code === "ru") return face0.name
        if (code === "ar") return face2.name
        if (code === "fr") return face0.name
        if (code === "de") return face0.name
        if (code === "es") return face0.name
        if (code === "pt") return face0.name
        if (code === "it") return face0.name
        if (code === "zh") return (face3.status === FontLoader.Ready ? "Noto Sans CJK SC" : face3.name)
        if (code === "zh-Hant") return (face3.status === FontLoader.Ready ? "Noto Sans CJK TC" : face3.name)
        if (code === "ja") return (face3.status === FontLoader.Ready ? "Noto Sans CJK JP" : face3.name)
        if (code === "ko") return (face3.status === FontLoader.Ready ? "Noto Sans CJK KR" : face3.name)
        if (code === "tr") return face0.name
        if (code === "uk") return face0.name
        if (code === "pl") return face0.name
        if (code === "cs") return face0.name
        if (code === "nl") return face0.name
        if (code === "hi") return face4.name
        if (code === "th") return face5.name
        if (code === "vi") return face0.name
        if (code === "ms") return face0.name
        if (code === "id") return face0.name
        if (code === "tl") return face0.name
        if (code === "km") return face6.name
        if (code === "my") return face7.name
        if (code === "fa") return face2.name
        if (code === "gu") return face8.name
        if (code === "ur") return face2.name
        if (code === "te") return face9.name
        if (code === "mr") return face4.name
        if (code === "bn") return face10.name
        if (code === "ta") return face11.name
        if (code === "bo") return face12.name
        if (code === "kk") return face0.name
        if (code === "mn") return face0.name
        if (code === "ug") return face2.name
        if (code === "yue") return (face3.status === FontLoader.Ready ? "Noto Sans CJK HK" : face3.name)
        return face0.name
    }
}
