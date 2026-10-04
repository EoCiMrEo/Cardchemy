"""Author the public, invented question-centric source-ranking packet.

This file is data preparation only. It never reads application data, imports a
model, or performs inference. The two splits use separate fictional document
families and question templates. The output is checked in before scoring.
"""
from __future__ import annotations

import json
from pathlib import Path

DESTINATION = (Path(__file__).resolve().parents[1] / 'backend/tests/fixtures/rag_eval'
               / 'source_ranker_listwise_public_v1.json')

# Every positive group has one useful window and three same-topic windows that
# omit the requested relation, condition, or entity. The negatives are passages,
# not deliberately malformed strings. Each group is one fictional PDF handbook.
POSITIVE = {
    'calibration': {
        'acronym_expansion': [
            ('What does RVM stand for in the workshop checklist?',
             'Workshop checklist: RVM means Return Valve Marker, the tag placed on the return pipe.',
             'Workshop checklist: RVM tags are blue and are inspected before a pressure test.',
             'Workshop checklist: Return valves must be closed before a pressure test.',
             'Workshop checklist: RPM means Rotation Per Minute on the motor readout.'),
            ('What is KPC expanded to on the kiln log?',
             'Kiln log abbreviations: KPC is Kiln Pressure Check; record it before lighting the burner.',
             'Kiln log: KPC is recorded on the line below the burner temperature.',
             'Kiln log: pressure checks are required at the start of every shift.',
             'Kiln log abbreviations: KTC means Kiln Temperature Check.'),
        ],
        'definition': [
            ('What is pot life for the two-part sealant?',
             'Sealant terms: pot life is the interval after mixing during which the two-part sealant remains usable.',
             'The two-part sealant is supplied in separate resin and hardener containers.',
             'The mixed sealant should be applied with a clean, dry spatula.',
             'Cure time is the period after application until the sealant reaches its specified hardness.'),
            ('What is a catch basin in the greenhouse drain plan?',
             'Greenhouse drainage: a catch basin is a recessed chamber that collects runoff before it enters the outlet pipe.',
             'Greenhouse drainage: inspect the catch basin grate for leaves each Friday.',
             'Runoff from the greenhouse roof flows toward the western outlet pipe.',
             'A soakaway is a gravel-filled pit that disperses water into surrounding soil.'),
        ],
        'mechanism': [
            ('How does the bypass valve prevent pressure spikes in the wash line?',
             'Wash line: when inlet pressure rises, a spring-loaded bypass valve opens and diverts flow to the return tank.',
             'Wash line: the bypass valve is mounted after the pump and has a red service cap.',
             'Wash line: pressure spikes are visible as sudden jumps on the inlet gauge.',
             'Wash line: the return tank stores water for the next cleaning cycle.'),
            ('How does the compost aerator move air through the pile?',
             'Compost aerator: its fan pushes air into perforated pipes beneath the pile, and air rises through the material.',
             'The compost aerator fan sits beside the covered pile.',
             'Turning the pile weekly helps prevent compacted layers.',
             'The perforated pipes should be checked for blocked holes after each batch.'),
        ],
        'measurement': [
            ('What does the clamp gauge measure on the press?',
             'Press instruments: the clamp gauge measures force applied by the press jaws to the workpiece.',
             'Press instruments: the clamp gauge is mounted above the lower jaw.',
             'The press jaws must be cleaned before a new workpiece is placed.',
             'The dial thermometer measures oil temperature in the hydraulic reservoir.'),
            ('What does the green color strip indicate in the water test?',
             'Water test: a green strip indicates that dissolved chlorine is within the specified operating band.',
             'Water test: place a strip in the sample for exactly three seconds.',
             'The water sample is taken from the lower tap.',
             'A blue strip indicates that the sample temperature is below the normal band.'),
        ],
        'reason': [
            ('Why is the stage riser vented during paint drying?',
             'Paint drying: the riser is vented so solvent vapor can escape instead of accumulating beneath the deck.',
             'The stage riser has two removable ventilation grilles.',
             'The riser is painted after the rehearsal furniture has been removed.',
             'Keep the stage door closed to prevent dust from settling on fresh paint.'),
            ('Why are seed trays shaded at midday?',
             'Seedling care: shade the trays at midday because direct sun can overheat the shallow soil and damage new roots.',
             'Seed trays are placed on the east bench after watering.',
             'Midday is the scheduled time to check the greenhouse thermometer.',
             'Shade cloth is stored beside the seed-tray bench.'),
        ],
        'process': [
            ('What are the steps for replacing the lab air filter?',
             'Filter replacement: switch off the blower, release the two latches, remove the used filter, fit the new one, then close the latches.',
             'The lab air filter is inspected every Monday.',
             'The replacement filter has an arrow showing airflow direction.',
             'A dirty filter can increase blower noise and reduce airflow.'),
            ('How should the workshop wind vane be calibrated?',
             'Wind vane calibration: align the pointer with true north, loosen the base collar, rotate the zero mark to the pointer, then tighten the collar.',
             'The workshop wind vane is fixed to a short roof mast.',
             'Wind vane readings are recorded after the rain gauge is emptied.',
             'Avoid climbing onto the roof during high winds.'),
        ],
        'property_limitation': [
            ('What limitation does woven hose have when routed around tight corners?',
             'Woven hose: tight bends can kink the inner tube and restrict flow despite the outer braid remaining intact.',
             'Woven hose has a braided outer layer and a replaceable metal coupling.',
             'Route the hose away from hot motor housings.',
             'Rigid pipe is harder to install around corners than flexible hose.'),
            ('What property makes the ceramic sleeve suitable near the burner?',
             'Burner assembly: the ceramic sleeve tolerates high heat without softening, protecting the nearby cable.',
             'The ceramic sleeve surrounds the cable beside the burner.',
             'Replace a sleeve if its outer surface has a visible crack.',
             'The steel guard protects the burner from accidental impact.'),
        ],
        'application_example': [
            ('When would the narrow nozzle be used in the cleaning kit?',
             'Cleaning kit: use the narrow nozzle to remove dust from grooves between closely spaced machine fins.',
             'The narrow nozzle fits the hand vacuum and is stored in the lower drawer.',
             'The cleaning kit includes brushes, a hand vacuum, and two nozzles.',
             'The broad nozzle is used on large flat floors.'),
            ('Where is the blue-tag sensor used in the cold-room system?',
             'Cold room: the blue-tag sensor is installed at the door seal to detect when the door has been left ajar.',
             'The blue-tag sensor sends a status signal every five minutes.',
             'Cold-room sensors are checked during the weekly inspection.',
             'The red-tag sensor monitors compressor vibration.'),
        ],
    },
    'heldout': {
        'acronym_expansion': [
            ('A ferry entry is marked LCT. Expand that harbor-register code.',
             'Harbor register / code LCT\nFull term: Landing Clearance Time.\nUse: interval reserved for an arriving ferry.',
             'The harbor guide prints LCT beside each arriving ferry.',
             'Landing clearance is confirmed by radio before the ferry enters.',
             'LCP expands to Landing Clearance Permit on the dock notice.'),
            ('An archive box bears SFB. Supply the complete label term.',
             'Archive label key / SFB\nFull term: Sealed Folio Box.\nContents: unbound historic sheets.',
             'An SFB label must include the shelf number and handling date.',
             'Historic sheets are stored flat in labeled boxes.',
             'SFC stands for Sealed Folio Cover in the archive label key.'),
        ],
        'definition': [
            ('For a timetable reader, explain what headway refers to.',
             'Tram timetable glossary / headway\nMeaning: time gap between successive trams passing the same stop.',
             'The timetable lists headway in minutes for peak and off-peak service.',
             'Successive trams pass the central stop on a numbered route.',
             'Dwell time is the time a tram remains stopped for boarding.'),
            ('The museum rule says buffer zone. Describe the area it denotes.',
             'Museum storage / buffer zone\nMeaning: clear perimeter around an artifact; keeps neighboring items from touching it.',
             'Mark the buffer zone with removable floor tape.',
             'Artifact labels must face the aisle for inventory checks.',
             'A quarantine shelf holds newly arrived artifacts before inspection.'),
        ],
        'mechanism': [
            ('Trace the closing action of the sprinkler diaphragm once the control pulse stops.',
             'Sprinkler control sequence\nPulse ends → upper chamber refills with pressure → diaphragm seats → flow closes.',
             'The sprinkler diaphragm can be inspected beneath the valve cap.',
             'The irrigation controller sends a short electrical pulse to the valve.',
             'The sprinkler pipe feeds four garden beds at the far wall.'),
            ('In damp air, identify the physical action that opens the archive cabinet flap.',
             'Archive cabinet response / damp air\nMoisture-sensitive strip lengthens → linkage pulls → humidity flap opens.',
             'The humidity flap sits behind the cabinet ventilation slots.',
             'Staff log cabinet humidity before opening the door.',
             'The cabinet fan circulates air while the door is closed.'),
        ],
        'measurement': [
            ('Name the measured quantity and unit reported by the deck radiometer.',
             'Deck instrument record\nRadiometer | observed quantity: incoming solar irradiance | unit: W/m².',
             'The deck radiometer is mounted above the navigation cabin.',
             'Record the radiometer reading before sunrise and at noon.',
             'The barometer reports atmospheric pressure in hectopascals.'),
            ('A river sample is tested with a turbidity tube. What sample property does its reading represent?',
             'River sampling record\nTurbidity tube | reading: water cloudiness from suspended particles | indicator: depth where marker disappears.',
             'Rinse the turbidity tube with river water before filling it.',
             'River samples are taken upstream of the road bridge.',
             'The conductivity meter estimates dissolved ionic content.'),
        ],
        'reason': [
            ('The observatory covers its telescope mirror before dawn. What damage is this meant to prevent?',
             'Observatory mirror procedure\nAction: cover before dawn.\nRisk avoided: moisture condensing on reflective coating.',
             'The observatory stores mirror covers beside the telescope mount.',
             'Dawn observations end when the sky becomes too bright.',
             'The mirror coating is cleaned only during scheduled maintenance.'),
            ('The transit depot separates battery packs on its shelves. Explain the safety reason.',
             'Transit depot shelf rule\nAction: keep battery packs apart.\nReason: reduce heat transfer from a failing pack.',
             'Battery packs are stored on steel shelves in the depot.',
             'Record the battery pack serial number before storage.',
             'The depot inspects charging cables for wear each month.'),
        ],
        'process': [
            ('List the order of crew actions before reading the harbor tide gauge.',
             'Harbor tide gauge checklist\n1. Remove cap. 2. Clear intake debris. 3. Wait for chamber to settle. 4. Record scale.',
             'The tide gauge scale is painted on the harbor wall.',
             'Reading times are listed on the crew shift sheet.',
             'Do not service the gauge during an active storm warning.'),
            ('Describe the sequence for bringing a sealed archive packet back to room conditions.',
             'Archive thawing checklist\n1. Leave sealed packet at room temperature until dry. 2. Open outer sleeve. 3. Inspect for moisture.',
             'Sealed archive packets are stored on the upper freezer shelf.',
             'Use clean gloves when handling paper after thawing.',
             'Freezing can temporarily halt insect activity in a packet.'),
        ],
        'property_limitation': [
            ('A display panel may be installed in a humid room. Explain the laminate limitation relevant to that choice.',
             'Display panel material note\nLaminate + sustained humidity → swollen edge → layer separation. Avoid damp rooms.',
             'The laminate panel is mounted on a lightweight frame.',
             'Check the panel surface for scratches before an exhibition.',
             'A glass panel is heavier than a laminate panel.'),
            ('A film package needs a sharp fold. Which material property makes the biodegradable film unsuitable?',
             'Packaging film handling\nMaterial: biodegradable film.\nAt sharp creases: brittle fracture. Use a wide fold radius.',
             'The biodegradable film is supplied on large rolls.',
             'The film can be printed with water-based ink.',
             'A reinforced cloth wrap withstands repeated folding.'),
        ],
        'application_example': [
            ('The night-service cart needs low-light visibility. Identify where reflective tape goes and why.',
             'Night-service cart marking plan\nRear corners: reflective tape. Purpose: visibility to drivers in low light.',
             'Reflective tape is replaced whenever its surface peels.',
             'The cart is kept in the depot between night shifts.',
             'A flashing lamp is mounted on the cart roof.'),
            ('For the aquarium return flow, state the task assigned to the ion exchange column.',
             'Aquarium return loop\nIon exchange column → dissolved nitrate removal before water returns to tank.',
             'The ion exchange column is installed after the coarse filter.',
             'Aquarium water is tested each morning before feeding.',
             'The charcoal cartridge removes odors from the supply line.'),
        ],
    },
}

# No-useful controls contain four plausible same-topic passages without the
# requested relationship. Calibration and heldout use independent inventions.
NO_USEFUL = {
    'calibration': {
        'acronym_expansion': ('What does RPK stand for on the workshop order?', [
            'Workshop order: RPK appears beside the quantity to be packed.',
            'Workshop order: packing begins after the final inspection.',
            'RPK labels are printed on blue paper for the shipping desk.',
            'Workshop order key: RPL means Return Packing Label.']),
        'definition': ('What is a bypass shelf in the kiln room?', [
            'Kiln room: the bypass shelf stands near the side entrance.',
            'Staff place spare kiln gloves on a wall shelf.',
            'The bypass fan is serviced twice a year.',
            'Kiln room labels use large print for safety notices.']),
        'mechanism': ('How does the workshop chime detect a blocked chute?', [
            'The workshop chime is checked before the chute is loaded.',
            'A blocked chute requires the operator to stop the conveyor.',
            'The chime makes a short tone during the morning test.',
            'A separate light indicates that the conveyor door is open.']),
        'measurement': ('What does the yellow dial quantify in the wash station?', [
            'The wash station has a yellow dial above the sink.',
            'Technicians wipe the dial glass each Friday.',
            'The blue dial reports rinse-water temperature.',
            'The wash station records each cleaning cycle in a log.']),
        'reason': ('Why is the south vent closed during seed drying?', [
            'The south vent is closed during seed drying.',
            'A humidity meter hangs near the drying trays.',
            'Seed drying begins when the trays have been cleaned.',
            'The north vent is opened to let warm air escape.']),
        'process': ('How is the red gauge zeroed before a press test?', [
            'The red gauge is read before and after every press test.',
            'A zero mark is printed on the gauge face.',
            'The press test requires a flat, dry workpiece.',
            'Technicians store spare gauges in the tool cabinet.']),
        'property_limitation': ('What limitation does the green coating have under ultraviolet light?', [
            'The green coating is applied to the outside panel.',
            'Protective eyewear is required when a UV lamp is used.',
            'The coating dries for six hours before handling.',
            'A blue coating resists abrasion during cleaning.']),
        'application_example': ('Where is the short copper sleeve used in the garden pump?', [
            'The short copper sleeve is listed in the garden pump parts box.',
            'The pump body has two hose connectors.',
            'A long rubber sleeve protects the outlet pipe.',
            'The garden pump runs once each morning.']),
    },
    'heldout': {
        'acronym_expansion': ('A DSR code appears in a harbor register. Provide its full phrase.', [
            'Harbor register: DSR appears in the arrival column.',
            'DSR entries are checked against the ferry manifest.',
            'The harbor register is archived each month.',
            'Harbor key: DTR means Dock Transit Record.']),
        'definition': ('The museum guide names a cold buffer. Describe what it denotes.', [
            'Museum guide: the cold buffer is inspected every Tuesday.',
            'Cold storage is used for certain sealed artifacts.',
            'The museum guide lists equipment near the loading door.',
            'A buffer pad cushions objects during transport.']),
        'mechanism': ('Trace how the ferry alarm detects a loose stern hatch.', [
            'The ferry alarm sounds during its scheduled self-test.',
            'A loose stern hatch must be secured before sailing.',
            'Crew inspect the alarm cable beside the hatch.',
            'A second alarm sounds when the bilge level is high.']),
        'measurement': ('Name the physical quantity monitored by the tram’s silver probe.', [
            'The silver probe is attached beneath the tram seat.',
            'Inspect the probe lead during the weekly service.',
            'The tram speed sensor reports wheel rotation.',
            'A replacement probe is kept at the depot.']),
        'reason': ('The archive cabinet light stays off overnight. Explain why.', [
            'The archive cabinet light is left off overnight.',
            'An evening guard checks the cabinet lock.',
            'Cabinet lighting is switched on before inventory.',
            'The archive workroom lights are dimmed at closing.']),
        'process': ('Give the leveling steps required before inspecting the telescope mount.', [
            'The telescope mount is inspected every six months.',
            'A bubble level is stored beside the mount.',
            'The inspection form has a field for the level reading.',
            'The mount bolts must remain accessible.']),
        'property_limitation': ('For salt-water exposure, identify the drawback of red sealing tape.', [
            'Red sealing tape marks the pipe joint below the deck.',
            'Wash salt from the deck after each voyage.',
            'The tape roll is kept in a dry locker.',
            'A different rubber gasket loses flexibility in cold weather.']),
        'application_example': ('Locate the amber valve’s role in the aquarium flow path.', [
            'The amber valve appears on the aquarium parts diagram.',
            'The aquarium has a return pipe and a drain pipe.',
            'An orange valve is used on the cleaning branch.',
            'The amber valve is checked during monthly maintenance.']),
    },
}

WEAKNESS_REASONS = {
    'acronym_expansion': (
        'Names the requested code without pairing it with its complete phrase.',
        'Describes nearby operations but gives no expansion for the requested code.',
        'Expands a different code, which cannot define the requested one.'),
    'definition': (
        'Uses the requested term without explaining its meaning.',
        'Gives surrounding workflow or location rather than a definition.',
        'Defines a neighboring term rather than the requested term.'),
    'mechanism': (
        'Locates the component but omits the causal action asked about.',
        'Names a trigger or outcome without tracing how the requested component acts.',
        'Describes a neighboring component or maintenance action instead.'),
    'measurement': (
        'Names or locates the instrument without stating its measured quantity.',
        'Describes sampling or timing without the requested readout meaning.',
        'States a quantity for a different instrument or indicator.'),
    'reason': (
        'Repeats the action or equipment without explaining why it is done.',
        'Provides a schedule or context without the reason for the action.',
        'Explains a separate precaution or maintenance task.'),
    'process': (
        'Mentions the equipment without giving the requested ordered steps.',
        'Offers one contextual detail, not the full procedure.',
        'Gives a safety or maintenance note rather than the requested sequence.'),
    'property_limitation': (
        'Identifies the material without the property or limitation asked about.',
        'Gives an adjacent usage or maintenance note, not that property.',
        'Attributes a property to a different material.'),
    'application_example': (
        'Names or stores the item without the requested use or placement.',
        'Describes the surrounding system without the item’s application.',
        'Gives an application for a different item.'),
}

NO_USEFUL_RATIONALES = {
    'calibration': {
        'acronym_expansion': 'No passage expands RPK; the RPL expansion belongs to a different code.',
        'definition': 'No passage defines bypass shelf; location and bypass fan are adjacent facts.',
        'mechanism': 'No passage explains a blocked-chute detection mechanism for the workshop chime.',
        'measurement': 'No passage says what the yellow dial measures; blue dial is another instrument.',
        'reason': 'No passage explains why the south vent is closed during seed drying.',
        'process': 'No passage gives steps to zero the red gauge before the press test.',
        'property_limitation': 'No passage states a UV limitation of green coating; blue coating is different.',
        'application_example': 'No passage identifies a use or placement for the short copper sleeve.',
    },
    'heldout': {
        'acronym_expansion': 'No passage expands DSR; DTR is another harbor code.',
        'definition': 'No passage defines the museum cold buffer; buffer pad is a different item.',
        'mechanism': 'No passage tells how the ferry alarm senses a loose stern hatch.',
        'measurement': 'No passage states the silver probe’s measured quantity; speed sensor is different.',
        'reason': 'No passage gives the reason for leaving the archive cabinet light off overnight.',
        'process': 'No passage gives the telescope-mount leveling sequence.',
        'property_limitation': 'No passage states red tape’s salt-water drawback; rubber gasket is different.',
        'application_example': 'No passage identifies the amber valve’s aquarium flow-path role.',
    },
}


HELDOUT_HEADINGS = {
    'acronym_expansion': ('Harbor register / LCT', 'Archive label key / SFB', 'Harbor register / DSR'),
    'definition': ('Tram timetable / headway', 'Museum storage / buffer zone',
                   'Museum guide / cold buffer'),
    'mechanism': ('Sprinkler valve / diaphragm', 'Archive cabinet / humidity flap',
                  'Ferry / stern hatch alarm'),
    'measurement': ('Deck instruments / radiometer', 'River sampling / turbidity tube',
                    'Tram service / silver probe'),
    'reason': ('Observatory / telescope mirror', 'Transit depot / battery packs',
               'Archive cabinet / overnight light'),
    'process': ('Harbor / tide gauge', 'Archive / sealed-packet thawing',
                'Observatory / telescope mount leveling'),
    'property_limitation': ('Display panel / laminate', 'Packaging / biodegradable film',
                            'Deck piping / red sealing tape'),
    'application_example': ('Night-service cart / reflective tape',
                            'Aquarium loop / ion exchange column', 'Aquarium flow / amber valve'),
}


def displayed_window(split: str, relation: str, group_number: int, window: str) -> str:
    if split == 'calibration':
        return window
    # Each of the four candidates in a heldout group receives the exact same
    # topic-specific shell. Do not add label-specific "adjacent" or "gold"
    # markers: the model must rank the relation stated in the entry itself.
    heading = HELDOUT_HEADINGS[relation][group_number-1]
    body = window.split('\n', 1)[1] if '\n' in window else window
    body = body.replace('\n', ' | ')
    return f'{heading}\nEntry: {body}'


def build():
    groups = []
    for split in ('calibration', 'heldout'):
        for relation_index, (relation, examples) in enumerate(POSITIVE[split].items()):
            for number, example in enumerate(examples, 1):
                question, *windows = example
                group_id = f'{split[0].upper()}-{relation}-{number}'
                # Rotate the source order. The useful position is balanced
                # across the four slots and cannot be recovered from the ID.
                shift = (relation_index + number - 1) % 4
                ordered = list(enumerate(windows, 1))
                ordered = ordered[shift:] + ordered[:shift]
                candidates = []
                for index, (original_index, raw_window) in enumerate(ordered, 1):
                    window = displayed_window(split, relation, number, raw_window)
                    candidates.append({
                        'candidate_id': f'{group_id}-{index}',
                        'document_id': f'{split}-fictional-{relation}-{number}-{index}',
                        'page_number': index, 'page_text': window,
                        'start_offset': 0, 'end_offset': len(window),
                        'useful': original_index == 1,
                        'rationale': (
                            'States the requested relation for the exact target and condition.'
                            if original_index == 1 else WEAKNESS_REASONS[relation][original_index-2]
                        ),
                    })
                groups.append({
                    'group_id': group_id, 'split': split, 'relation': relation,
                    'question': question, 'previous_question': None,
                    'source_family': ('calibration-workshop-prose' if split == 'calibration'
                                      else 'heldout-field-records'),
                    'template_family': ('calibration-direct-questions' if split == 'calibration'
                                        else 'heldout-indirect-tasks'),
                    'useful_available': True,
                    'candidates': candidates,
                })
        for relation, (question, windows) in NO_USEFUL[split].items():
            group_id = f'{split[0]}-{relation}-none'
            groups.append({
                'group_id': group_id, 'split': split, 'relation': relation,
                'question': question, 'previous_question': None,
                'source_family': ('calibration-workshop-prose' if split == 'calibration'
                                  else 'heldout-field-records'),
                'template_family': ('calibration-direct-questions' if split == 'calibration'
                                    else 'heldout-indirect-tasks'),
                'useful_available': False,
                'candidates': [
                    {'candidate_id': f'{group_id}-{index}',
                     'document_id': f'{split}-fictional-{relation}-none-{index}',
                     'page_number': index, 'page_text': displayed_window(split, relation, 3, window),
                     'start_offset': 0, 'end_offset': len(displayed_window(split, relation, 3, window)),
                     'useful': False,
                     'rationale': NO_USEFUL_RATIONALES[split][relation]}
                    for index, window in enumerate(windows, 1)
                ],
            })
    return {
        'schema': 'source_ranker_listwise_public_v1',
        'provenance': 'Independent invented public relation examples; no private or application content.',
        'scope': 'Window-level relative ranking only; not SQL recall, PDF fidelity, or release evidence.',
        'groups': groups,
    }


if __name__ == '__main__':
    DESTINATION.write_text(json.dumps(build(), indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    print(f'Wrote {DESTINATION.name}: {len(build()["groups"])} groups')
