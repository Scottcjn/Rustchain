#!/usr/bin/env python
"""
RustChain Proof of Antiquity Animated Explainer
Bounty: 50 RTC + 25 RTC bonus (Chinese subtitles)
https://github.com/Scottcjn/rustchain-bounties/issues/2304
"""

from manim import *

class ProofOfAntiquityExplanation(Scene):
    def construct(self):
        # Title slide
        title = Text("RustChain").scale(1.5)
        subtitle = Text("Proof of Antiquity\nHow It Works").scale(0.8)
        VGroup(title, subtitle).arrange(DOWN, buff=0.5)
        
        self.play(Write(title))
        self.play(Write(subtitle))
        self.wait(2)
        self.play(FadeOut(title), FadeOut(subtitle))

        # Part 1: The Problem
        self.problem_part()
        
        # Part 2: The Solution
        self.solution_part()
        
        # Part 3: How It Works
        self.how_it_works_part()
        
        # Part 4: Multiplier System
        self.multiplier_part()
        
        # Part 5: Why VMs can't cheat
        self.vm_part()
        
        # Part 6: Call to Action
        self.cta_part()

    def problem_part(self):
        title = Text("The Problem").scale(1.2).to_edge(UP)
        self.play(Write(title))

        # GPU Mining Centralization
        gpu_text = Text("GPU Mining → Centralization").next_to(title, DOWN, buff=0.5)
        gpu_centralized = VGroup(
            Rectangle(width=6, height=3),
            Text("Big Mining Pools", font_size=24).move_to(ORIGIN),
        )
        gpu_centralized.next_to(gpu_text, DOWN, buff=0.5)
        
        ewaste_text = text = Text("Old Hardware → E-Waste").next_to(gpu_centralized, DOWN, buff=0.8)
        ewaste_box = Rectangle(width=6, height=2)
        ewaste_box.next_to(ewaste_text, DOWN, buff=0.5)
        ewaste_label = Text("Working vintage hardware\nthrown away for new GPUs", font_size=20).move_to(ewaste_box.get_center())

        self.play(Write(gpu_text))
        self.play(Create(gpu_centralized[0]), Write(gpu_centralized[1]))
        self.play(Write(ewaste_text))
        self.play(Create(ewaste_box), Write(ewaste_label))
        self.wait(3)
        
        self.play(FadeOut(title), *[FadeOut(obj) for obj in [gpu_text, gpu_centralized, ewaste_text, ewaste_box, ewaste_label]])

    def solution_part(self):
        title = Text("The Solution: Proof of Antiquity").scale(1.2).to_edge(UP)
        self.play(Write(title))

        concept = Text(
            "Older hardware = Higher rewards\n"
            "Give new life to vintage computers",
            line_spacing=0.5,
            font_size=28
        ).next_to(title, DOWN, buff=0.8)

        self.play(Write(concept))
        self.wait(3)
        self.play(FadeOut(title), FadeOut(concept))

    def how_it_works_part(self):
        title = Text("How It Works").scale(1.2).to_edge(UP)
        self.play(Write(title))

        steps = VGroup(
            Text("1️⃣  Hardware Fingerprinting", font_size=32),
            Text("2️⃣  Attestation Submission", font_size=32),
            Text("3️⃣  Epoch Selection", font_size=32),
            Text("4️⃣  Reward Distribution", font_size=32),
        ).arrange(DOWN, aligned_edge=LEFT, buff=0.4)
        steps.next_to(title, DOWN, buff=0.8)

        for step in steps:
            self.play(Write(step))
            self.wait(1.5)

        self.wait(2)
        self.play(FadeOut(title), FadeOut(steps))

    def multiplier_part(self):
        title = Text("The Multiplier System").scale(1.2).to_edge(UP)
        self.play(Write(title))

        table = Table(
            [["Hardware", "Reward Multiplier"],
             ["PowerBook G4", "2.5x"],
             ["Power Mac G5", "2.0x"],
             ["Modern x86", "1.0x"],
             ["Virtual Machine", "~0x"]],
            include_outer_lines=True
        ).scale(0.8).next_to(title, DOWN, buff=0.5)

        self.play(Create(table))
        self.wait(4)
        
        explanation = Text(
            "Older = higher multiplier\n"
            "More chance to mine a block = more rewards",
            line_spacing=0.5,
            font_size=24
        ).next_to(table, DOWN, buff=0.5)
        self.play(Write(explanation))
        self.wait(3)

        self.play(FadeOut(title), FadeOut(table), FadeOut(explanation))

    def vm_part(self):
        title = Text("Why VMs Can't Cheat").scale(1.2).to_edge(UP)
        self.play(Write(title))

        fingerprint_text = Text(
            "Hardware fingerprinting measures\n"
            "instruction timing differences\n"
            "VMs have different timing signatures\n"
            "→ Automatically detected → Near zero multiplier",
            line_spacing=0.6,
            font_size=28
        ).next_to(title, DOWN, buff=0.8)

        self.play(Write(fingerprint_text))
        self.wait(4)

        self.play(FadeOut(title), FadeOut(fingerprint_text))

    def cta_part(self):
        title = Text("Ready to Start Mining?").scale(1.3).to_edge(UP)
        self.play(Write(title))

        qr = Rectangle(height=4, width=4).to_edge(DOWN, buff=0.5)
        qr_label = Text("Scan for latest miner", font_size=24).next_to(qr, UP, buff=0.5)
        
        url = Text("https://github.com/Scottcjn/RustChain", font_size=20).next_to(qr, DOWN, buff=0.5)

        self.play(Create(qr), Write(qr_label), Write(url))
        self.wait(3)

        logo_text = Text("RustChain").scale(1.2)
        self.play(
            *[FadeOut(obj) for obj in self.mobjects],
            run_time=1
        )
        self.play(Write(logo_text))
        self.wait(2)

        self.play(FadeOut(logo_text))


# Render command:
# manim -pql proof_of_antiquity.py ProofOfAntiquityExplanation -o proof_of_antiquity.mp4
