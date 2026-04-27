#! /usr/bin/env python3

"""Servo control module for Pilomar.

This module provides classes and functions to control servo motors
using the pigpio library. It supports threading for asynchronous
operation and precise timing for servo movements.
"""

import time
import threading

import pigpio



class DualStepperTracker:
    TICK_US = 200        # time resolution (5kHz timing grid)
    CHUNK_TIME = 0.05    # 50 ms waveform chunks

    def __init__(self, pi: pigpio.pi, az_step, az_dir, alt_step, alt_dir):
        self.pi = pi

        self.az_step = az_step
        self.az_dir = az_dir
        self.alt_step = alt_step
        self.alt_dir = alt_dir

        for p in [az_step, az_dir, alt_step, alt_dir]:
            pi.set_mode(p, pigpio.OUTPUT)

        self.az_rate = 0.0     # steps/sec
        self.alt_rate = 0.0

        self.az_phase = 0.0
        self.alt_phase = 0.0

        self.running = True
        threading.Thread(target=self._loop, daemon=True).start()

    # -------- public control ----------
    def set_rates(self, az_steps_per_sec, alt_steps_per_sec):
        self.az_rate = az_steps_per_sec
        self.alt_rate = alt_steps_per_sec

        self.pi.write(self.az_dir, 1 if az_steps_per_sec >= 0 else 0)
        self.pi.write(self.alt_dir, 1 if alt_steps_per_sec >= 0 else 0)

    # -------- realtime generator ----------
    def _loop(self):
        ticks = int(self.CHUNK_TIME * 1e6 / self.TICK_US)

        while self.running:
            pulses = []

            az_rate = abs(self.az_rate)
            alt_rate = abs(self.alt_rate)

            az_inc = az_rate * self.TICK_US / 1e6
            alt_inc = alt_rate * self.TICK_US / 1e6

            for _ in range(ticks):
                on_mask = 0

                self.az_phase += az_inc
                self.alt_phase += alt_inc

                if self.az_phase >= 1:
                    on_mask |= (1 << self.az_step)
                    self.az_phase -= 1

                if self.alt_phase >= 1:
                    on_mask |= (1 << self.alt_step)
                    self.alt_phase -= 1

                if on_mask:
                    pulses.append(pigpio.pulse(on_mask, 0, self.TICK_US//2))
                    pulses.append(pigpio.pulse(0, on_mask, self.TICK_US//2))
                else:
                    pulses.append(pigpio.pulse(0,0,self.TICK_US))

            self.pi.wave_add_generic(pulses)
            wid = self.pi.wave_create()
            self.pi.wave_send_once(wid)

            while self.pi.wave_tx_busy():
                time.sleep(0.001)

            self.pi.wave_delete(wid)


if __name__ == "__main__":

    # Lets run some basic motion tests,
    # simple forward back on 1 axis, then the other,
    # then both together.

    pi = pigpio.pi()

    tracker = DualStepperTracker(
        pi,
        az_step=21, az_dir=20,
        alt_step=6,  alt_dir=5
    )

    # sidereal base rates
    tracker.set_rates(
        az_steps_per_sec = 400.456,
        alt_steps_per_sec = 100.114
    )
    val = input("Press Enter to continue...")
    print(f'{hex(ord(val))}')