#include <unity.h>
#include <string.h>
#include <ds2.h>

// MS43 reply to 12 05 0B 03 1F, from drive2.ru/l/9797918 (idle, warm-ish engine)
static const uint8_t REPLY[] = {
    0x12, 0x2D, 0xA0, 0x02, 0xEB, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x31, 0x6F, 0x9A, 0x82,
    0x74, 0xBE, 0x01, 0xEC, 0xFE, 0x66, 0x54, 0xF4, 0x8A, 0x78, 0x88, 0x78, 0x90, 0x78, 0x1E,
    0xFE, 0xFE, 0x34, 0x34, 0x10, 0xCB, 0x0E, 0xC6, 0x05, 0x05, 0x0D, 0x2E, 0xD1, 0x87, 0xBD,
};
static const uint8_t REQ[] = {0x12, 0x05, 0x0B, 0x03, 0x1F};

void setUp() {}
void tearDown() {}

static Ds2Parser::Result feedAll(Ds2Parser& p, const uint8_t* b, size_t n) {
    Ds2Parser::Result r = Ds2Parser::MORE;
    for (size_t i = 0; i < n && r == Ds2Parser::MORE; i++) r = p.feed(b[i]);
    return r;
}

void test_checksum() {
    TEST_ASSERT_EQUAL_HEX8(0x1F, ds2Checksum(REQ, 4));
    TEST_ASSERT_EQUAL_HEX8(0xBD, ds2Checksum(REPLY, sizeof(REPLY) - 1));
}

void test_build() {
    const uint8_t body[] = {0x0B, 0x03};
    uint8_t out[8];
    TEST_ASSERT_EQUAL(5, ds2Build(0x12, body, 2, out, sizeof(out)));
    TEST_ASSERT_EQUAL_HEX8_ARRAY(REQ, out, 5);
    TEST_ASSERT_EQUAL(0, ds2Build(0x12, body, 2, out, 4));
}

void test_parse_with_echo_byte_by_byte() {
    Ds2Parser p;
    p.start(REQ, sizeof(REQ), 0x12);
    TEST_ASSERT_EQUAL(Ds2Parser::MORE, feedAll(p, REQ, sizeof(REQ)));
    TEST_ASSERT_EQUAL(Ds2Parser::DONE, feedAll(p, REPLY, sizeof(REPLY)));
    TEST_ASSERT_EQUAL(sizeof(REPLY), p.length());
    TEST_ASSERT_EQUAL_HEX8_ARRAY(REPLY, p.frame(), sizeof(REPLY));
}

void test_bad_echo() {
    Ds2Parser p;
    p.start(REQ, sizeof(REQ), 0x12);
    TEST_ASSERT_EQUAL(Ds2Parser::MORE, p.feed(0x12));
    TEST_ASSERT_EQUAL(Ds2Parser::BAD_ECHO, p.feed(0x07));
}

void test_garbage_before_header_is_skipped() {
    Ds2Parser p;
    p.start(nullptr, 0, 0x12);
    const uint8_t junk[] = {0x00, 0xFF, 0x55};
    TEST_ASSERT_EQUAL(Ds2Parser::MORE, feedAll(p, junk, sizeof(junk)));
    TEST_ASSERT_EQUAL(Ds2Parser::DONE, feedAll(p, REPLY, sizeof(REPLY)));
}

void test_bad_sum() {
    uint8_t bad[sizeof(REPLY)];
    memcpy(bad, REPLY, sizeof(REPLY));
    bad[sizeof(bad) - 1] ^= 0x01;
    Ds2Parser p;
    p.start(nullptr, 0, 0x12);
    TEST_ASSERT_EQUAL(Ds2Parser::BAD_SUM, feedAll(p, bad, sizeof(bad)));
}

void test_bad_len() {
    Ds2Parser p;
    p.start(nullptr, 0, 0x12);
    p.feed(0x12);
    TEST_ASSERT_EQUAL(Ds2Parser::BAD_LEN, p.feed(0x03));
    p.start(nullptr, 0, 0x12);
    p.feed(0x12);
    TEST_ASSERT_EQUAL(Ds2Parser::BAD_LEN, p.feed(0xFF));
}

void test_decode_ms43_status() {
    Ms43Status s;
    TEST_ASSERT_TRUE(ms43DecodeStatus(REPLY, sizeof(REPLY), s));
    TEST_ASSERT_EQUAL(747, s.rpm);
    TEST_ASSERT_EQUAL(0, s.speed);
    TEST_ASSERT_FLOAT_WITHIN(0.01f, 0.0f, s.pedalDeg);
    TEST_ASSERT_FLOAT_WITHIN(0.01f, 0.0f, s.throttleDeg);
    TEST_ASSERT_FLOAT_WITHIN(0.01f, 35.25f, s.intakeC);
    TEST_ASSERT_FLOAT_WITHIN(0.01f, 67.5f, s.coolantC);
    TEST_ASSERT_FLOAT_WITHIN(0.01f, 13.71f, s.vbat);
}

void test_decode_rejects_nack_and_short() {
    Ms43Status s;
    uint8_t nack[] = {0x12, 0x04, 0xB0, 0x00};
    nack[3] = ds2Checksum(nack, 3);
    TEST_ASSERT_FALSE(ms43DecodeStatus(nack, sizeof(nack), s));
    TEST_ASSERT_FALSE(ms43DecodeStatus(REPLY, 20, s));
}

void test_pedal_percent() {
    TEST_ASSERT_EQUAL(0, ms43PedalPercent(0));
    TEST_ASSERT_EQUAL(50, ms43PedalPercent(MS43_PEDAL_FULL_DEG / 2));
    TEST_ASSERT_EQUAL(100, ms43PedalPercent(500));
    TEST_ASSERT_EQUAL(0, ms43PedalPercent(-3));
}

void test_parse_hex() {
    uint8_t out[8];
    TEST_ASSERT_EQUAL(4, ds2ParseHex("12 05 0b 03", out, sizeof(out)));
    TEST_ASSERT_EQUAL_HEX8_ARRAY(REQ, out, 4);
    TEST_ASSERT_EQUAL(2, ds2ParseHex("120B", out, sizeof(out)));
    TEST_ASSERT_EQUAL(0, ds2ParseHex("zz", out, sizeof(out)));
    TEST_ASSERT_EQUAL(0, ds2ParseHex("123", out, sizeof(out)));
    TEST_ASSERT_EQUAL(0, ds2ParseHex("12 34 56", out, 2));
}

int main() {
    UNITY_BEGIN();
    RUN_TEST(test_checksum);
    RUN_TEST(test_build);
    RUN_TEST(test_parse_with_echo_byte_by_byte);
    RUN_TEST(test_bad_echo);
    RUN_TEST(test_garbage_before_header_is_skipped);
    RUN_TEST(test_bad_sum);
    RUN_TEST(test_bad_len);
    RUN_TEST(test_decode_ms43_status);
    RUN_TEST(test_decode_rejects_nack_and_short);
    RUN_TEST(test_pedal_percent);
    RUN_TEST(test_parse_hex);
    return UNITY_END();
}
