"""Words for passcodes: short Japanese words that are easy to type on a phone."""
import secrets

WORDS = """
akari akane amagi ame aoba arashi asahi asuka ayame azuki biwa bonsai budo chawan chidori daikon
dango donguri enoki fubuki fuji fukuro furin futon geta ginga gohan goma hagi hakama hana hanabi
haru hasu hayate hibari hikari hinoki hiroba hoshi hotaru ibuki ichigo icho inari inaho iroha ishi
iwa izumi kabuto kaede kagami kaki kame kami kasa kasumi katana kawa kaze keyaki kibi kiku kinoko
kiri kitsune koban kodama koi koke kokoro koma kome konbu kotori kuma kumo kuri kurumi kusa kuzu
maki matcha matsu mayu meiji mikan minato miso mizu mochi momiji momo mori musubi nagi nami nashi
negi neko niji nishiki nori nozomi ochiai oden ohashi okayu omochi onsen origami oto ringo roka
sakana sakura same sango sansho satsuki sazanami seiza sekai semi shiba shika shima shiro sora
soba sudachi sugi suika sumi suzu tabi taiko take tako tamago tanuki tatami tengu tenki tofu tomo
tora torii tsubaki tsuki tsuru uchiwa udon ume umi unagi urara usagi uzura wakame wasabi washi
yagura yama yanagi yoru yuki yukata yume yuzu zakuro zen zori kanji kendo ninja sushi tempura
manga haiku kimono kotatsu bento ramen sake taiyo hokori ikada ishigaki jinja kairo kakashi kamome
karuta kintsugi kogarashi komorebi kurenai michi mikado mizore nadeshiko noren obi oboro sabi
sensu shizuku shoji sukiyaki tanabata tsukimi uguisu wabi yamabuki yugen yuzuriha
""".split()


def passcode(count=5):
    return "-".join(secrets.choice(WORDS) for _ in range(count))


def normalize(text):
    """Forgiving about case, spaces and punctuation: 'Sakura kumo' == 'sakura-kumo'."""
    return "-".join("".join(c if c.isalpha() else " " for c in str(text).lower()).split())
