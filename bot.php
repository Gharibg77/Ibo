<?php

// =========================
// 1) إعداد البوت
// =========================
$TOKEN = "ضع-توكن-البوت-هنا";
$AI_KEY = "ضع-مفتاح-Google-Gemini-هنا"; 
$apiURL = "https://api.telegram.org/bot$TOKEN/";

// =========================
// 2) جلب الرسالة
// =========================
$update = json_decode(file_get_contents("php://input"), true);

$message = $update["message"]["text"] ?? "";
$chat_id = $update["message"]["chat"]["id"] ?? "";
$file_id = $update["message"]["photo"][count($update["message"]["photo"]) - 1]["file_id"] ?? null;
$document_id = $update["message"]["document"]["file_id"] ?? null;

// =========================
// 3) دالة إرسال رسالة
// =========================
function sendMessage($chat_id, $text) {
    global $apiURL;
    file_get_contents($apiURL."sendMessage?chat_id=$chat_id&text=".urlencode($text));
}

// =========================
// 4) ذكاء اصطناعي Google Gemini
// =========================
function ai_reply($prompt){
    global $AI_KEY;

    $data = [
        "contents" => [
            ["parts" => [["text" => $prompt]]]
        ]
    ];

    $payload = json_encode($data);

    $result = file_get_contents(
        "https://generativelanguage.googleapis.com/v1/models/gemini-pro:generateContent?key=$AI_KEY",
        false,
        stream_context_create([
            "http" => [
                "method" => "POST",
                "header" => "Content-Type: application/json",
                "content" => $payload
            ]
        ])
    );

    $res = json_decode($result, true);
    return $res["candidates"][0]["content"]["parts"][0]["text"] ?? "❌ خطأ في توليد الرد!";
}

// =========================
// 5) تحميل فيديو يوتيوب (API مجاني)
// =========================
function download_youtube($url){
    $api = "https://yt-api-leo.vercel.app/api/ytmp4?url=".urlencode($url);
    $res = json_decode(file_get_contents($api), true);

    if(isset($res["url"])) {
        return $res["url"];
    } else {
        return false;
    }
}

// =========================
// 6) استقبال الصور وتحليلها
// =========================
function analyze_image($chat_id, $file_id){
    global $apiURL, $AI_KEY;

    // الحصول على رابط الصورة
    $file = json_decode(file_get_contents($apiURL."getFile?file_id=$file_id"), true);
    $file_path = $file["result"]["file_path"];
    $url = "https://api.telegram.org/file/bot".TOKEN."/$file_path";

    // طلب إلى Google Gemini Vision
    $payload = json_encode([
        "contents" => [
            ["parts" => [
                ["text" => "حلل هذه الصورة بالتفصيل"],
                ["image_url" => $url]
            ]]
        ]
    ]);

    $result = file_get_contents(
        "https://generativelanguage.googleapis.com/v1beta/models/gemini-pro-vision:generateContent?key=$AI_KEY",
        false,
        stream_context_create([
            "http" => [
                "method" => "POST",
                "header" => "Content-Type: application/json",
                "content" => $payload
            ]
        ])
    );

    $res = json_decode($result, true);
    $text = $res["candidates"][0]["content"]["parts"][0]["text"] ?? "❌ فشل التحليل";

    sendMessage($chat_id, $text);
}

// =========================
// 7) التعامل مع الرسائل
// =========================

if($message){

    // أمر /start
    if($message == "/start"){
        sendMessage($chat_id, "👋 أهلاً! أنا بوت PHP خارق:\n\n- ذكاء اصطناعي\n- تحليل صور\n- تحميل فيديوهات\n- دردشة كاملة\n\nأكتب أي سؤال!");
    }

    // تحميل يوتيوب
    elseif(strpos($message, "youtube.com") !== false || strpos($message, "youtu.be") !== false){
        sendMessage($chat_id, "⏳ جاري جلب رابط التحميل...");

        $res = download_youtube($message);
        if($res){
            sendMessage($chat_id, "✔️ رابط جاهز:\n$res");
        } else {
            sendMessage($chat_id, "❌ حدث خطأ في التحميل.");
        }
    }

    // ذكاء اصطناعي — الرد على الكلام
    else {
        $reply = ai_reply($message);
        sendMessage($chat_id, $reply);
    }
}

// تحليل صورة
if($file_id){
    sendMessage($chat_id, "⏳ استقبلت صورة… جاري التحليل");
    analyze_image($chat_id, $file_id);
}

// استقبال الملفات
if($document_id){
    sendMessage($chat_id, "📄 تم استلام ملف… (التحليل قيد التطوير)");
}

?>