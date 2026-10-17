#include <unity.h>
#include <power_latch.h>

void setUp() {}
void tearDown() {}

const float MAX_A = 15.0f;

void test_conversions() {
    TEST_ASSERT_FLOAT_WITHIN(0.1f, 29.95f, isVoltsToAmps(0.62f));
    TEST_ASSERT_FLOAT_WITHIN(0.01f, 13.68f, vbatFromAdc(2.4f));
}

void test_normal_current_never_trips() {
    PowerLatch l;
    for (uint32_t t = 0; t < 5000; t += 10) TEST_ASSERT_EQUAL(PowerLatch::NONE, l.update(t, 10.0f, 0.2f, MAX_A));
}

void test_inrush_shorter_than_hold_is_ignored() {
    PowerLatch l;
    for (uint32_t t = 0; t < 90; t += 10) TEST_ASSERT_EQUAL(PowerLatch::NONE, l.update(t, 40.0f, 0.83f, MAX_A));
    for (uint32_t t = 90; t < 1000; t += 10) TEST_ASSERT_EQUAL(PowerLatch::NONE, l.update(t, 5.0f, 0.1f, MAX_A));
}

void test_sustained_overcurrent_trips_after_hold() {
    PowerLatch l;
    TEST_ASSERT_EQUAL(PowerLatch::NONE, l.update(1000, 20.0f, 0.4f, MAX_A));
    TEST_ASSERT_EQUAL(PowerLatch::NONE, l.update(1090, 20.0f, 0.4f, MAX_A));
    TEST_ASSERT_EQUAL(PowerLatch::OVERCURRENT, l.update(1100, 20.0f, 0.4f, MAX_A));
}

void test_fault_voltage_trips_first() {
    PowerLatch l;
    TEST_ASSERT_EQUAL(PowerLatch::NONE, l.update(0, 140.0f, 3.0f, MAX_A));
    TEST_ASSERT_EQUAL(PowerLatch::NONE, l.update(40, 140.0f, 3.0f, MAX_A));
    TEST_ASSERT_EQUAL(PowerLatch::FAULT, l.update(50, 140.0f, 3.0f, MAX_A));
}

void test_millis_wraparound() {
    PowerLatch l;
    uint32_t t0 = 0xFFFFFFC0u;
    TEST_ASSERT_EQUAL(PowerLatch::NONE, l.update(t0, 20.0f, 0.4f, MAX_A));
    TEST_ASSERT_EQUAL(PowerLatch::NONE, l.update(t0 + 50, 20.0f, 0.4f, MAX_A));
    TEST_ASSERT_EQUAL(PowerLatch::OVERCURRENT, l.update(t0 + 100, 20.0f, 0.4f, MAX_A));
}

void test_reset_restarts_hold() {
    PowerLatch l;
    l.update(0, 20.0f, 0.4f, MAX_A);
    l.reset();
    TEST_ASSERT_EQUAL(PowerLatch::NONE, l.update(150, 20.0f, 0.4f, MAX_A));
    TEST_ASSERT_EQUAL(PowerLatch::OVERCURRENT, l.update(250, 20.0f, 0.4f, MAX_A));
}

int main() {
    UNITY_BEGIN();
    RUN_TEST(test_conversions);
    RUN_TEST(test_normal_current_never_trips);
    RUN_TEST(test_inrush_shorter_than_hold_is_ignored);
    RUN_TEST(test_sustained_overcurrent_trips_after_hold);
    RUN_TEST(test_fault_voltage_trips_first);
    RUN_TEST(test_millis_wraparound);
    RUN_TEST(test_reset_restarts_hold);
    return UNITY_END();
}
