<?php
// Test : ce serveur peut-il joindre les sites des ministères algériens ?
// À déposer dans public_html via le Gestionnaire de fichiers de cPanel, à ouvrir dans le navigateur,
// puis à supprimer. Aucun paramètre n'est lu : le script interroge seulement les adresses ci-dessous.
header('Content-Type: text/html; charset=utf-8');
header('X-Robots-Tag: noindex');

$sites = [
    "Ministère de l'Industrie pharmaceutique" => 'https://www.miph.gov.dz/fr/feed/',
    'Ministère du Commerce' => 'https://www.commerce.gov.dz/fr',
    "Ministère de l'Industrie" => 'https://www.industrie.gov.dz',
    'Journal officiel (témoin)' => 'https://www.joradp.dz',
];

function lire($url, $delai = 20) {
    $c = curl_init($url);
    curl_setopt_array($c, [
        CURLOPT_RETURNTRANSFER => true,
        CURLOPT_FOLLOWLOCATION => true,
        CURLOPT_MAXREDIRS => 5,
        CURLOPT_CONNECTTIMEOUT => $delai,
        CURLOPT_TIMEOUT => $delai + 20,
        CURLOPT_USERAGENT => 'VeillePharmaDZ/1.0 (test)',
    ]);
    $corps = curl_exec($c);
    $r = [
        'code' => curl_getinfo($c, CURLINFO_HTTP_CODE),
        'duree' => round(curl_getinfo($c, CURLINFO_TOTAL_TIME), 1),
        'taille' => $corps === false ? 0 : strlen($corps),
        'erreur' => curl_error($c),
        'corps' => $corps,
    ];
    curl_close($c);
    return $r;
}

$ip = lire('https://ipinfo.io/json', 10);
$info = $ip['corps'] ? json_decode($ip['corps'], true) : null;
$lieu = $info ? htmlspecialchars(($info['city'] ?? '?') . ', ' . ($info['country'] ?? '?') . ' – ' . ($info['org'] ?? '')) : 'inconnu';

echo '<!doctype html><meta name="viewport" content="width=device-width,initial-scale=1">';
echo '<title>Test ministères</title><body style="font-family:system-ui,sans-serif;max-width:720px;margin:24px auto;padding:0 16px">';
echo '<h2>Test des sites des ministères</h2><p>Serveur situé : <b>' . $lieu . '</b></p><table cellpadding="8" style="border-collapse:collapse">';
$ok = 0;
foreach ($sites as $nom => $url) {
    $r = lire($url);
    $bon = $r['code'] >= 200 && $r['code'] < 400 && $r['taille'] > 500;
    $ok += $bon && strpos($nom, 'témoin') === false ? 1 : 0;
    $detail = $bon ? "réponse {$r['code']}, {$r['taille']} octets, {$r['duree']} s"
                   : ($r['erreur'] ? htmlspecialchars($r['erreur']) : "réponse {$r['code']}");
    echo '<tr style="border-top:1px solid #ddd"><td>' . ($bon ? '✅' : '❌') . '</td><td><b>' . htmlspecialchars($nom)
        . '</b><br><small>' . htmlspecialchars($url) . '</small></td><td>' . $detail . '</td></tr>';
}
echo '</table><h3>' . ($ok === 3 ? '✅ Les 3 ministères répondent : ce serveur peut servir de relais.'
    : "Résultat : $ok ministère(s) sur 3 répondent.") . '</h3>';
echo '<p>Faites une capture de cette page, puis supprimez ce fichier.</p></body>';
