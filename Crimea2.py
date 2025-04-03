import pandas as pd
import numpy as np
import json
from datetime import datetime, date
import re
import dash
from dash import dcc, html, dash_table
import dash_bootstrap_components as dbc
from dash.dependencies import Input, Output, State
import plotly.express as px
import plotly.graph_objects as go
import networkx as nx
import dash_cytoscape as cyto  # Import Cytoscape
import os
import traceback
import uuid  # For Cytoscape element generation if needed

# Load Cytoscape extensions - important for layouts
cyto.load_extra_layouts()

# Enable debug mode
debug_mode = True

# ------------------------------------------------------------------------------
# DATA PREPARATION
# ------------------------------------------------------------------------------
def parse_date(date_str):
    original_date_str = date_str
    try:
        date_str = date_str.strip()
        # Simple range match: "18-20 Feb 2014" -> use the first day
        range_match_simple = re.match(r"(\d{1,2})\s*-\s*\d{1,2}\s+(\w{3})\s+(\d{4})", date_str)
        if range_match_simple:
            day_start, month, year = range_match_simple.groups()
            date_str = f"{day_start} {month} {year}"
        # Complex range match if needed
        range_match_complex = re.match(r"(\d{1,2}\s+\w{3})\s*-\s*\d{1,2}\s+\w{3}\s+(\d{4})", date_str)
        if range_match_complex:
            day_month_start, year = range_match_complex.groups()
            date_str = f"{day_month_start} {year}"
        formats_to_try = ["%d %b %Y"]
        for fmt in formats_to_try:
            try:
                return datetime.strptime(date_str, fmt)
            except ValueError:
                continue
        print(f"Warning: Could not parse date string '{original_date_str}' (processed as '{date_str}') with known formats.")
        return datetime(2014, 2, 27)
    except Exception as e:
        print(f"Error during date parsing for: '{original_date_str}', Processed str: '{date_str}'. Error: {e}")
        return datetime(2014, 2, 27)

# ------------------------------------------------------------------------------
# FULL DATA LISTS
# ------------------------------------------------------------------------------
events = [
    {
        "date": "21 Nov 2013", "title": "Ukraine Drops EU Deal; Protests Begin (Euromaidan)", "type": "Political",
        "actors": ["Ukraine (Yanukovych gov't)", "EU", "Russia"], "location": "Kyiv (Ukraine)",
        "summary": "Ukraine's government abruptly suspends plans to sign an EU Association Agreement, reportedly under Russian pressure. The move sparks the largest protests since 2004, as pro-European demonstrators gather in Kyiv's Independence Square (launching the 'Euromaidan' movement)."
    },
    {
        "date": "18-20 Feb 2014", "title": "Deadly Clashes in Kyiv ('Maidan Massacre')", "type": "Civil Unrest",
        "actors": ["Protesters", "Ukraine security forces"], "location": "Kyiv",
        "summary": "After months of mostly peaceful protest, violence peaks in Kyiv. Security forces open fire on demonstrators, including sniper attacks on Feb 20, killing dozens. In ~72 hours nearly 100 protesters are killed. These events undermine President Viktor Yanukovych's authority and become a tipping point in Ukraine's revolution."
    },
    {
        "date": "22 Feb 2014", "title": "Ukrainian President Ousted by Parliament", "type": "Political",
        "actors": ["Ukraine (Parliament)", "Viktor Yanukovych", "Oleksandr Turchynov"], "location": "Kyiv",
        "summary": "President Yanukovych flees Kyiv amid the turmoil. Ukraine's parliament votes to remove Yanukovych from power. Speaker Oleksandr Turchynov is appointed acting President until new elections. A new pro-Western interim government forms, as Yanukovych denounces the events as a coup from exile."
    },
    {
        "date": "23 Feb 2014", "title": "Pro-Russian Rally in Crimea; Parallel Authority in Sevastopol", "type": "Civil/Political",
        "actors": ["Sevastopol locals", "Aleksei Chaly", "Crimean Tatars"], "location": "Sevastopol, Simferopol (Crimea)",
        "summary": "As Kiev's new authorities take charge, pro-Russian sentiment surges in Crimea. In Sevastopol, thousands rally waving Russian flags and reject the 'Kiev coup.' The crowd 'elects' Russian businessman Aleksei Chaly as de facto mayor, forming local 'self-defense' units. In Simferopol (Crimea's capital), a smaller pro-Ukraine demonstration takes place in support of the Maidan movement. Tensions begin to split the region along political and ethnic lines."
    },
    {
        "date": "26 Feb 2014", "title": "Clashes at Crimean Parliament between Rival Rallies", "type": "Civil Unrest",
        "actors": ["Mejlis of Crimean Tatars", "Russian Unity party", "Crimean Parliament"], "location": "Simferopol (Crimea)",
        "summary": "Competing protests collide outside the Crimean legislature. Over 10,000 Crimean Tatars and pro-Ukraine activists rally to support Ukraine's territorial integrity, facing off against a smaller pro-Russian crowd calling for Crimea's secession. Scuffles break out; police struggle to maintain order. In the chaos, at least 30 people are injured and 2 die (one from a stampede, one from heart attack). The parliament's emergency session is aborted. This 'Day of Resistance' later becomes a symbol of Crimeans opposed to separation."
    },
    {
        "date": "27 Feb 2014", "title": "Armed Men Seize Crimean Parliament; New PM Installed", "type": "Military/Political",
        "actors": ["Unmarked Russian special forces", "Crimean Parliament", "Sergey Aksyonov"], "location": "Simferopol",
        "summary": "Pre-dawn raids: Unidentified gunmen in military gear (widely believed to be Russian special forces) storm the Crimean parliament and government buildings, raising Russian flags. Under the guns, Crimean lawmakers convene and vote out the regional government, installing Sergey Aksyonov (leader of the pro-Russia 'Russian Unity' party) as Prime Minister. Aksyonov announces he's in charge of Crimea's security forces and hastily calls for a referendum on Crimea's status (initially set for May). This bloodless coup marks the start of open separatist control in Crimea."
    },
    {
        "date": "28 Feb 2014", "title": "Russian Troops and 'Self-Defense' Forces Take Control", "type": "Military",
        "actors": ["Russian Armed Forces (Black Sea Fleet)", "Crimean self-defense militias"], "location": "Throughout Crimea (Simferopol, Sevastopol)",
        "summary": "Unmarked Russian soldiers begin securing strategic sites across Crimea. Heavily armed troops occupy Simferopol airport and roads, and Russian Navy personnel block naval bases in Sevastopol. By day's end, Crimea's administrative centers, airports, ports, and telecommunication hubs are under armed control, cutting the peninsula off from mainland Ukraine. Moscow still denies its troops are involved, calling the fighters 'local self-defense forces,' but their equipment and coordination indicate a Russian military operation. Ukrainian bases in Crimea are surrounded, though no major gunfire occurs."
    },
    {
        "date": "1 Mar 2014", "title": "Russia Authorizes Use of Force in Ukraine", "type": "Political/Military",
        "actors": ["Sergey Aksyonov", "Vladimir Putin", "Russian Federation Council"], "location": "Simferopol; Moscow",
        "summary": "Aksyonov (Crimea's new de facto PM) appeals directly to Putin to 'help ensure peace and order' in Crimea, effectively requesting Russian military assistance. Within hours, President Vladimir Putin asks Russia's legislature for authority to intervene. The Federation Council unanimously approves Putin's request to use the Russian Armed Forces on Ukrainian territory. This gives formal Russian legal cover to the ongoing military presence. In Kiev, acting President Turchynov places Ukraine's military on high alert and calls Russia's move 'a declaration of war.'"
    },
    {
        "date": "3-8 Mar 2014", "title": "Standoff – Ukraine Isolated; OSCE Observers Blocked", "type": "Diplomatic/Military",
        "actors": ["Ukraine interim government", "OSCE", "NATO", "Russian forces"], "location": "Crimea borders",
        "summary": "Ukraine's new government, unable to fight militarily in Crimea, pursues diplomacy. OSCE sends an unarmed military observer mission to Crimea, but armed men at checkpoints refuse entry. On 8 March, warning shots are fired to turn back OSCE observers at Armyansk checkpoint. Meanwhile NATO's leadership warns Russia to pull back. Russian forces entrench their positions, demanding Ukrainian units surrender. The interim Kiev leadership continues to insist Crimea remains Ukrainian, but on the ground their authority is effectively null."
    },
    {
        "date": "6 Mar 2014", "title": "Crimean Parliament Votes to Secede and Join Russia", "type": "Political/Legal",
        "actors": ["Crimean Supreme Council (Parliament)", "Crimean gov't (Aksyonov)", "Russia"], "location": "Simferopol",
        "summary": "Under armed guard, 78 of 100 deputies vote to secede from Ukraine and 'reunify' with Russia. They also move up the region's status referendum to just 10 days away (16 March), changing the ballot to offer a choice between joining Russia or restoring Crimea's 1992 constitution. Crimean officials frame the vote as merely 'confirming' their decision. Kiev's government and nearly all international observers condemn this as illegal. Russia welcomes the decision, while accelerating plans to facilitate Crimea's absorption."
    },
    {
        "date": "11 Mar 2014", "title": "Crimea's 'Declaration of Independence'", "type": "Political/Legal",
        "actors": ["Crimean Parliament & Sevastopol Council"], "location": "Simferopol; Sevastopol",
        "summary": "Anticipating a pro-Russian outcome in the upcoming referendum, Crimea's regional parliament (joined by Sevastopol's city council) passes a Declaration of Independence from Ukraine. The document states that if the referendum approves joining Russia, Crimea shall be an independent state and will request entry into the Russian Federation. Russia signals that this 'Republic of Crimea' would be eligible for accession under Russian law, citing the Kosovo precedent."
    },
    {
        "date": "15 Mar 2014", "title": "UN Security Council Draft Resolution Vetoed by Russia", "type": "Diplomatic",
        "actors": ["United Nations Security Council (P5: Russia, US, UK, France, China)"], "location": "New York (UN HQ)",
        "summary": "On the eve of the referendum, Western powers bring a resolution to the UN Security Council urging states not to recognize the planned vote. In the vote, 13 of 15 Council members back the resolution, but Russia vetoes it (China abstains). The draft stated the referendum 'can have no validity' and called on states to refrain from recognizing any change of Crimea's status. Russia's veto isolates Moscow diplomatically."
    },
    {
        "date": "16 Mar 2014", "title": "Crimean Referendum Held Under Occupation", "type": "Political/Legal",
        "actors": ["Crimean de facto authorities", "Crimean voters", "Russia"], "location": "Crimea (all districts)",
        "summary": "Crimea holds a hastily organized referendum on its status, under heavy military presence with checkpoints at polling stations. The choice is union with Russia or reverting to Crimea's 1992 constitution (no option to remain with Ukraine). The official result claims 95–97% in favor of joining Russia with an 83% turnout; however, most Western governments denounce the vote as illegitimate."
    },
    {
        "date": "17 Mar 2014", "title": "Crimea Moves to Annexation; Western Sanctions Begin", "type": "Political & Intl. Response",
        "actors": ["Crimean Parliament", "Russia", "EU", "USA"], "location": "Simferopol; Moscow; Brussels; Washington",
        "summary": "The day after the referendum, Crimea's parliament formally declares independence and appeals to join the Russian Federation. President Putin recognizes the 'Republic of Crimea' as a sovereign state, clearing a legal path to annexation. In response, the United States and European Union impose their first sanctions, including asset freezes and travel bans, while Ukraine recalls its ambassadors from Moscow."
    },
    {
        "date": "18 Mar 2014", "title": "Treaty of Accession: Russia Annexes Crimea", "type": "Diplomatic/Legal",
        "actors": ["Vladimir Putin", "Sergey Aksyonov", "Russian Parliament"], "location": "Moscow",
        "summary": "In a celebratory Kremlin ceremony, Putin and Crimean separatist leaders sign the Treaty of Accession, formally annexing Crimea and Sevastopol into the Russian Federation. Western governments protest that the move violates international law and Ukraine's sovereignty. Shortly after, armed men storm a Ukrainian military base, marking the first combat fatality."
    },
    {
        "date": "20-21 Mar 2014", "title": "Annexation Legalized in Russian Law", "type": "Legal",
        "actors": ["Russian State Duma & Federation Council"], "location": "Moscow",
        "summary": "Russia's Federal Assembly ratifies the accession treaty. On 20 March, the State Duma votes overwhelmingly and on 21 March the Federation Council unanimously approves it. Putin signs the final law, absorbing Crimea and Sevastopol as new subjects of the Russian Federation."
    },
    {
        "date": "24 Mar 2014", "title": "G7 Nations Suspend Russia from G8", "type": "Diplomatic",
        "actors": ["G7 (USA, UK, France, Germany, Italy, Canada, Japan) & EU"], "location": "The Hague (Netherlands)",
        "summary": "Leaders of the G7 expel Russia from the G8 forum, canceling the planned Sochi summit and moving meetings to Brussels as a G7-only event. This action symbolizes Russia's growing diplomatic isolation."
    },
    {
        "date": "27 Mar 2014", "title": "UN General Assembly Deems Referendum Invalid", "type": "Diplomatic/Legal",
        "actors": ["UN General Assembly (193 member states)"], "location": "New York (UN HQ)",
        "summary": "The UN General Assembly votes 100–11 (with 58 abstentions) to affirm Ukraine's territorial integrity and declare the referendum void. The resolution calls on states not to recognize any change in Crimea's status, highlighting Russia's international isolation."
    },
    {
        "date": "15 Apr 2014", "title": "Kyiv Declares Crimea 'Occupied Territory'", "type": "Legal/Political",
        "actors": ["Ukraine (Parliament & Gov't)", "Arseniy Yatsenyuk"], "location": "Kyiv (Ukraine)",
        "summary": "Ukraine's parliament adopts Law 1207-VII, designating Crimea and Sevastopol as 'temporarily occupied' by Russia. Acting Prime Minister Yatsenyuk vows that 'Crimea has been, is, and will be Ukrainian,' reinforcing non-recognition even as Russian control continues."
    },
    {
        "date": "22 Apr - 3 May 2014", "title": "Tatar Leader Barred; Standoff at Crimea Border", "type": "Political/Human Rights",
        "actors": ["Mustafa Dzhemilev", "Crimean authorities", "Crimean Tatar community"], "location": "Crimea (Armyansk checkpoint)",
        "summary": "Crimea's authorities ban veteran Tatar leader Mustafa Dzhemilev from entering for five years. When Dzhemilev attempts to return on 3 May, thousands of Crimean Tatars gather at the border, leading to a tense standoff as security units block his entry. In the aftermath, over 100 Tatars are charged with administrative offenses."
    },
    {
        "date": "16-18 May 2014", "title": "Defying Ban, Tatars Commemorate Deportation Anniversary", "type": "Civil/Human Rights",
        "actors": ["Crimean Tatars (Mejlis)", "Sergey Aksyonov (Crimea PM)"], "location": "Simferopol (Crimea)",
        "summary": "Despite a decree banning mass gatherings, thousands of Tatars defy the ban on 18 May to commemorate their 1944 deportation. Tatar leaders address the crowd as authorities watch, underscoring their precarious situation under Russian occupation."
    },
    {
        "date": "25 May 2014", "title": "New Ukrainian President Elected, Vows to Reclaim Crimea", "type": "Political",
        "actors": ["Petro Poroshenko", "Ukrainian voters", "Russian gov't"], "location": "Ukraine (nationwide)",
        "summary": "An early presidential election is held. Petro Poroshenko wins decisively and, during his inauguration on 7 June, declares 'Crimea was, is, and will be Ukrainian.' His stance reinforces Ukraine's long-term claim despite Russia's administrative control."
    }
]

actors = [
    {"name": "Russia (Russian Federation)", "type": "Country (Aggressor)", "role": "Initiated and executed the annexation of Crimea. Deployed covert troops ('little green men') and authorized force via parliamentary vote. Integrated Crimea as a federal subject after the referendum. President Putin framed the takeover as correcting a historical wrong.", "events": ["Russian Troops and 'Self-Defense' Forces Take Control", "Russia Authorizes Use of Force in Ukraine", "Treaty of Accession: Russia Annexes Crimea"]},
    {"name": "Ukraine (post-revolution interim government)", "type": "Country (Victim State)", "role": "Opposed separatist moves at every step. Declared Russia's actions a military invasion and maintained that Crimea remained Ukrainian, passing laws designating it 'occupied.'", "events": ["Ukrainian President Ousted by Parliament", "Standoff – Ukraine Isolated; OSCE Observers Blocked", "Kyiv Declares Crimea 'Occupied Territory'"]},
    {"name": "United States", "type": "Country (International Responder)", "role": "Led Western condemnation and sanctions. Imposed travel bans and asset freezes on Russian officials and separatist leaders.", "events": ["UN Security Council Draft Resolution Vetoed by Russia", "Crimea Moves to Annexation; Western Sanctions Begin", "G7 Nations Suspend Russia from G8"]},
    {"name": "European Union (EU) and G7", "type": "Supranational Union / Economic bloc", "role": "Condemned Russia's actions and implemented coordinated sanctions. Declared the referendum illegal and suspended Russia from the G8.", "events": ["Crimea Moves to Annexation; Western Sanctions Begin", "G7 Nations Suspend Russia from G8"]},
    {"name": "United Nations", "type": "International Organization", "role": "Served as a global forum; passed Resolution 68/262 affirming Ukraine's territorial integrity and declaring the referendum void.", "events": ["UN Security Council Draft Resolution Vetoed by Russia", "UN General Assembly Deems Referendum Invalid"]},
    {"name": "NATO (North Atlantic Treaty Organization)", "type": "Military Alliance", "role": "Condemned Russia's intervention as a breach of international law and boosted defenses in Eastern Europe.", "events": ["Standoff – Ukraine Isolated; OSCE Observers Blocked"]},
    {"name": "OSCE (Organization for Security & Co-operation in Europe)", "type": "International Organization", "role": "Deployed observers to monitor events in Crimea, though they were blocked by Russian forces.", "events": ["Standoff – Ukraine Isolated; OSCE Observers Blocked"]},
    {"name": "Crimean Supreme Council (Parliament)", "type": "Regional Legislative Body", "role": "Seized by armed men and used as a rubber-stamp to vote for secession and join Russia.", "events": ["Armed Men Seize Crimean Parliament; New PM Installed", "Crimean Parliament Votes to Secede and Join Russia", "Crimea's 'Declaration of Independence'", "Crimean Referendum Held Under Occupation"]},
    {"name": "City of Sevastopol Administration", "type": "Local Government (City)", "role": "Formed a parallel administration; elected Aleksei Chaly as de facto mayor.", "events": ["Pro-Russian Rally in Crimea; Parallel Authority in Sevastopol", "Crimea's 'Declaration of Independence'"]},
    {"name": "Russian Armed Forces (Black Sea Fleet)", "type": "Military", "role": "Physically occupied Crimea by seizing key sites and blockading Ukrainian bases.", "events": ["Russian Troops and 'Self-Defense' Forces Take Control", "Standoff – Ukraine Isolated; OSCE Observers Blocked"]},
    {"name": "Crimean Tatars and Mejlis", "type": "Ethnic/Cultural Group", "role": "Strongly opposed the annexation. Organized protests and later faced repression.", "events": ["Clashes at Crimean Parliament between Rival Rallies", "Tatar Leader Barred; Standoff at Crimea Border", "Defying Ban, Tatars Commemorate Deportation Anniversary"]},
    {"name": "Crimean 'Self-Defense' Forces", "type": "Paramilitary Militia", "role": "Local militias that operated alongside Russian troops to secure the region.", "events": ["Russian Troops and 'Self-Defense' Forces Take Control", "Tatar Leader Barred; Standoff at Crimea Border"]},
    {"name": "Ukraine (Yanukovych gov't)", "type": "Country (Pre-Revolution Gov't)", "role": "The government before Euromaidan climax.", "events": ["Ukraine Drops EU Deal; Protests Begin (Euromaidan)"]},
    {"name": "EU", "type": "Supranational Union", "role": "Intended partner for the EU Association Agreement.", "events": ["Ukraine Drops EU Deal; Protests Begin (Euromaidan)"]},
    {"name": "Protesters", "type": "Group (Civil)", "role": "Euromaidan demonstrators.", "events": ["Deadly Clashes in Kyiv ('Maidan Massacre')"]},
    {"name": "Ukraine security forces", "type": "State Force", "role": "Security forces under Yanukovych.", "events": ["Deadly Clashes in Kyiv ('Maidan Massacre')"]},
    {"name": "Ukraine (Parliament)", "type": "National Legislative Body", "role": "The legislature that ousted Yanukovych.", "events": ["Ukrainian President Ousted by Parliament"]},
    {"name": "Sevastopol locals", "type": "Group (Civil)", "role": "Pro-Russian residents of Sevastopol.", "events": ["Pro-Russian Rally in Crimea; Parallel Authority in Sevastopol"]},
    {"name": "Russian Unity party", "type": "Political Party", "role": "Minor pro-Russian party led by Aksyonov.", "events": ["Clashes at Crimean Parliament between Rival Rallies"]},
    {"name": "Unmarked Russian special forces", "type": "Military (Covert)", "role": "Initial troops seizing key sites ('Little Green Men').", "events": ["Armed Men Seize Crimean Parliament; New PM Installed"]},
    {"name": "Crimean self-defense militias", "type": "Paramilitary Militia", "role": "Militias supporting the takeover.", "events": ["Russian Troops and 'Self-Defense' Forces Take Control"]},
    {"name": "Russian Federation Council", "type": "National Legislative Body (Upper House)", "role": "Approved the use of force.", "events": ["Russia Authorizes Use of Force in Ukraine"]},
    {"name": "Ukraine interim government", "type": "National Government (Interim)", "role": "Formed after Yanukovych fled.", "events": ["Standoff – Ukraine Isolated; OSCE Observers Blocked"]},
    {"name": "Russian forces", "type": "Military", "role": "General term for Russian troops.", "events": ["Standoff – Ukraine Isolated; OSCE Observers Blocked"]},
    {"name": "Crimean gov't (Aksyonov)", "type": "Regional Government (De Facto)", "role": "The separatist government installed on 27 Feb.", "events": ["Crimean Parliament Votes to Secede and Join Russia"]},
    {"name": "Aleksei Chaly", "type": "Regional Leader (De Facto)", "role": "Elected as de facto mayor of Sevastopol.", "events": ["Pro-Russian Rally in Crimea; Parallel Authority in Sevastopol", "Crimea's 'Declaration of Independence'"]},
    {"name": "Barack Obama", "type": "Country (International Responder)", "role": "Imposed sanctions and led international opposition.", "events": ["UN Security Council Draft Resolution Vetoed by Russia", "Crimea Moves to Annexation; Western Sanctions Begin", "G7 Nations Suspend Russia from G8"]},
]

individuals = [
    {"name": "Vladimir Putin", "role": "President of Russia", "description": "Principal architect of the annexation", "involvement": "Putin directed the strategy to take Crimea: on 22–23 Feb he convened security chiefs and declared 'we must start working on returning Crimea to Russia.' He deployed special forces and later signed the accession treaty on 18 Mar, framing the move as correcting a historical injustice.", "events": ["Russia Authorizes Use of Force in Ukraine", "Treaty of Accession: Russia Annexes Crimea"]},
    {"name": "Sergey Aksyonov", "role": "Crimean Prime Minister", "description": "Pro-Russian politician installed as leader of Crimea", "involvement": "Elevated on 27 Feb during the coup at the parliament, he consolidated local power and called for the 16 Mar referendum. He later signed the accession treaty.", "events": ["Armed Men Seize Crimean Parliament; New PM Installed", "Russia Authorizes Use of Force in Ukraine", "Crimean Parliament Votes to Secede and Join Russia", "Treaty of Accession: Russia Annexes Crimea"]},
    {"name": "Viktor Yanukovych", "role": "President of Ukraine until 22 Feb 2014", "description": "Ousted president whose downfall set the stage", "involvement": "His removal triggered events in both Kyiv and Crimea. He later resurfaced in Russia claiming legitimacy.", "events": ["Ukrainian President Ousted by Parliament"]},
    {"name": "Oleksandr Turchynov", "role": "Acting President of Ukraine", "description": "Interim head of state after Yanukovych's ouster", "involvement": "Faced the challenge of Crimea and mobilized Ukrainian forces and diplomacy, while avoiding armed escalation.", "events": ["Ukrainian President Ousted by Parliament", "Standoff – Ukraine Isolated; OSCE Observers Blocked"]},
    {"name": "Barack Obama", "role": "President of the United States", "description": "Led the international response", "involvement": "Warned Russia of costs for intervention and coordinated sanctions with the EU.", "events": ["UN Security Council Draft Resolution Vetoed by Russia", "Crimea Moves to Annexation; Western Sanctions Begin", "G7 Nations Suspend Russia from G8"]},
    {"name": "Mustafa Dzhemilev", "role": "Former Chairman of Crimean Tatar Mejlis", "description": "Iconic leader of the Crimean Tatars", "involvement": "Urged peaceful resistance and boycotted the referendum; later was barred from Crimea, sparking a tense border standoff.", "events": ["Tatar Leader Barred; Standoff at Crimea Border"]},
    {"name": "Refat Chubarov", "role": "Chairman of the Mejlis of Crimean Tatars", "description": "Leader of the Crimean Tatar community", "involvement": "Coordinated resistance, organized protests, and defied bans on commemorations.", "events": ["Clashes at Crimean Parliament between Rival Rallies", "Defying Ban, Tatars Commemorate Deportation Anniversary"]},
    {"name": "Aleksei Chaly", "role": "De facto Mayor of Sevastopol", "description": "Local pro-Russian businessman", "involvement": "Installed as mayor by pro-Russian crowds; organized self-defense units and coordinated with Russian forces.", "events": ["Pro-Russian Rally in Crimea; Parallel Authority in Sevastopol", "Crimea's 'Declaration of Independence'"]},
    {"name": "Arseniy Yatsenyuk", "role": "Acting Prime Minister of Ukraine", "description": "Head of the interim government", "involvement": "Vowed that Crimea remains Ukrainian and signed the occupied territory law.", "events": ["Kyiv Declares Crimea 'Occupied Territory'"]}
]

causal_links = [
    {"source_event": "Ukraine Drops EU Deal; Protests Begin (Euromaidan)", "target_event": "Deadly Clashes in Kyiv ('Maidan Massacre')", "relationship": "Escalation", "description": "The suspension of EU agreement plans sparked initial protests that escalated into deadly violence."},
    {"source_event": "Deadly Clashes in Kyiv ('Maidan Massacre')", "target_event": "Ukrainian President Ousted by Parliament", "relationship": "Direct Causation", "description": "The loss of life and chaos led to Yanukovych's removal."},
    {"source_event": "Ukrainian President Ousted by Parliament", "target_event": "Pro-Russian Rally in Crimea; Parallel Authority in Sevastopol", "relationship": "Reaction", "description": "The ousting of Yanukovych triggered pro-Russian mobilization in Crimea."},
    {"source_event": "Pro-Russian Rally in Crimea; Parallel Authority in Sevastopol", "target_event": "Clashes at Crimean Parliament between Rival Rallies", "relationship": "Polarization", "description": "Initial demonstrations led to counter-protests and clashes at the parliament."},
    {"source_event": "Clashes at Crimean Parliament between Rival Rallies", "target_event": "Armed Men Seize Crimean Parliament; New PM Installed", "relationship": "Pretext", "description": "The unrest provided a pretext for Russian forces to seize the parliament."},
    {"source_event": "Armed Men Seize Crimean Parliament; New PM Installed", "target_event": "Russian Troops and 'Self-Defense' Forces Take Control", "relationship": "Expansion", "description": "After seizing the parliament, Russian forces expanded control over Crimea."},
    {"source_event": "Russian Troops and 'Self-Defense' Forces Take Control", "target_event": "Russia Authorizes Use of Force in Ukraine", "relationship": "Retroactive Legalization", "description": "Force was later legally authorized by the Russian parliament."},
    {"source_event": "Russia Authorizes Use of Force in Ukraine", "target_event": "Standoff – Ukraine Isolated; OSCE Observers Blocked", "relationship": "Military Enforcement", "description": "Authorization allowed Russian forces to block international observers."},
    {"source_event": "Standoff – Ukraine Isolated; OSCE Observers Blocked", "target_event": "Crimean Parliament Votes to Secede and Join Russia", "relationship": "Political Cover", "description": "The absence of external oversight enabled a vote for secession."},
    {"source_event": "Crimean Parliament Votes to Secede and Join Russia", "target_event": "Crimea's 'Declaration of Independence'", "relationship": "Legal Preparation", "description": "The vote was followed by a formal declaration to legitimize the move."},
    {"source_event": "Crimea's 'Declaration of Independence'", "target_event": "UN Security Council Draft Resolution Vetoed by Russia", "relationship": "Diplomatic Confrontation", "description": "The declaration triggered diplomatic action which was vetoed by Russia."},
    {"source_event": "UN Security Council Draft Resolution Vetoed by Russia", "target_event": "Crimean Referendum Held Under Occupation", "relationship": "Diplomatic Shield", "description": "The veto removed obstacles for the referendum."},
    {"source_event": "Crimean Referendum Held Under Occupation", "target_event": "Crimea Moves to Annexation; Western Sanctions Begin", "relationship": "Direct Causation", "description": "The referendum result led to the declaration of annexation and subsequent sanctions."},
    {"source_event": "Crimea Moves to Annexation; Western Sanctions Begin", "target_event": "Treaty of Accession: Russia Annexes Crimea", "relationship": "Formalization", "description": "The annexation was formalized by signing the treaty."},
    {"source_event": "Treaty of Accession: Russia Annexes Crimea", "target_event": "Annexation Legalized in Russian Law", "relationship": "Legal Implementation", "description": "The treaty was ratified by the Russian parliament."},
    {"source_event": "Annexation Legalized in Russian Law", "target_event": "G7 Nations Suspend Russia from G8", "relationship": "International Consequence", "description": "The legal ratification triggered diplomatic isolation measures."},
    {"source_event": "G7 Nations Suspend Russia from G8", "target_event": "UN General Assembly Deems Referendum Invalid", "relationship": "Diplomatic Escalation", "description": "The G7 action led to the UN resolution condemning the referendum."},
    {"source_event": "UN General Assembly Deems Referendum Invalid", "target_event": "Kyiv Declares Crimea 'Occupied Territory'", "relationship": "Legal Response", "description": "Ukraine responded by designating Crimea as occupied territory."},
    {"source_event": "Kyiv Declares Crimea 'Occupied Territory'", "target_event": "Tatar Leader Barred; Standoff at Crimea Border", "relationship": "Tension Escalation", "description": "Ukraine's legal stance led to increased repression of dissent in Crimea."},
    {"source_event": "Tatar Leader Barred; Standoff at Crimea Border", "target_event": "Defying Ban, Tatars Commemorate Deportation Anniversary", "relationship": "Resistance", "description": "The barring of Tatar leaders spurred defiant commemorations."},
    {"source_event": "Defying Ban, Tatars Commemorate Deportation Anniversary", "target_event": "New Ukrainian President Elected, Vows to Reclaim Crimea", "relationship": "Policy Continuation", "description": "The continuing unrest influenced Ukraine's electoral choices."}
]

# --- DataFrame conversions and timeline preparation ---
events_df = pd.DataFrame(events)
events_df['date_parsed'] = events_df['date'].apply(parse_date)
events_df = events_df.sort_values('date_parsed').reset_index(drop=True)
timeline_df = events_df.copy()
timeline_df['date_str'] = timeline_df['date_parsed'].dt.strftime('%Y-%m-%d')
timeline_df['actors_str'] = timeline_df['actors'].apply(lambda x: ', '.join(x) if isinstance(x, list) else "")

actors_df = pd.DataFrame(actors)
actors_df['events'] = actors_df['events'].apply(lambda x: x if isinstance(x, list) else [])
individuals_df = pd.DataFrame(individuals)
individuals_df['events'] = individuals_df['events'].apply(lambda x: x if isinstance(x, list) else [])
causal_links_df = pd.DataFrame(causal_links)

# Define node colors by type
node_types = { "Event": "#4285F4", "Actor": "#EA4335", "Country": "#FBBC05", "Organization": "#34A853", "Individual": "#8F44AD", "Location": "#F39C12", "Method": "#3498DB", "Outcome": "#E74C3C" }

# Build nodes for events, actors, and individuals (for Cytoscape)
event_nodes = []
for _, event in events_df.iterrows():
    event_nodes.append({
        "id": event['title'],
        "label": event['title'],
        "type": "Event",
        "date": event['date'],
        "category": event['type'],
        "location": event['location'],
        "summary": event['summary'],
        "color": node_types["Event"]
    })

actor_nodes = []
for _, actor in actors_df.iterrows():
    color = node_types["Actor"]
    type_str = actor['type']
    if "Country" in type_str: color = node_types["Country"]
    elif any(sub in type_str for sub in ["Organization", "Union", "Military Alliance", "International Body", "Legislative Body", "State Force", "Military", "Paramilitary", "Group", "Party", "Community", "Government"]):
        color = node_types["Organization"]
    actor_nodes.append({
        "id": actor['name'],
        "label": actor['name'],
        "type": "Actor",
        "category": actor['type'],
        "role": actor['role'],
        "color": color
    })

individual_nodes = []
for _, individual in individuals_df.iterrows():
    individual_nodes.append({
        "id": individual['name'],
        "label": individual['name'],
        "type": "Individual",
        "role": individual['role'],
        "description": individual['description'],
        "involvement": individual['involvement'],
        "color": node_types["Individual"]
    })

# Build causal edges (between events)
causal_edges = []
for _, link in causal_links_df.iterrows():
    causal_edges.append({
        "source": link['source_event'],
        "target": link['target_event'],
        "label": link['relationship'],
        "description": link['description'],
        "type": "causal"
    })

# Build actor-event participation edges
actor_event_edges = []
event_titles = set(events_df['title'])
actor_names = set(actors_df['name'])
for _, actor in actors_df.iterrows():
    actor_name = actor['name']
    if isinstance(actor.get('events'), list):
        for event_title in actor['events']:
            if actor_name in actor_names and event_title in event_titles:
                actor_event_edges.append({
                    "source": actor_name,
                    "target": event_title,
                    "label": "involved_in",
                    "type": "participation"
                })

individual_event_edges = []
individual_names = set(individuals_df['name'])
for _, individual in individuals_df.iterrows():
    individual_name = individual['name']
    if isinstance(individual.get('events'), list):
        for event_title in individual['events']:
            if individual_name in individual_names and event_title in event_titles:
                individual_event_edges.append({
                    "source": individual_name,
                    "target": event_title,
                    "label": "participated_in",
                    "type": "participation"
                })

all_nodes = event_nodes + actor_nodes + individual_nodes
all_edges = causal_edges + actor_event_edges + individual_event_edges

# ------------------------------------------------------------------------------
# DASH APPLICATION SETUP
# ------------------------------------------------------------------------------
app = dash.Dash(__name__, external_stylesheets=[dbc.themes.BOOTSTRAP], suppress_callback_exceptions=True)
server = app.server

# Add this for debugging
app.config.suppress_callback_exceptions = True

# ------------------------------------------------------------------------------
# HELPER FUNCTIONS FOR CYTOSCAPE
# ------------------------------------------------------------------------------
default_stylesheet = [
    {'selector': 'node', 'style': {
        'label': 'data(label)',
        'font-size': '10px',
        'width': 'mapData(size, 5, 30, 5, 30)',
        'height': 'mapData(size, 5, 30, 5, 30)'
    }},
    {'selector': '[type = "Event"]', 'style': {'background-color': node_types['Event'], 'shape': 'ellipse'}},
    {'selector': '[type = "Country"]', 'style': {'background-color': node_types['Country'], 'shape': 'rectangle'}},
    {'selector': '[type = "Organization"]', 'style': {'background-color': node_types['Organization'], 'shape': 'rectangle'}},
    {'selector': '[type = "Individual"]', 'style': {'background-color': node_types['Individual'], 'shape': 'diamond'}},
    {'selector': '[type = "Actor"]', 'style': {'background-color': node_types['Actor'], 'shape': 'rectangle'}},
    {'selector': 'edge', 'style': {
        'label': 'data(label)',
        'font-size': '8px',
        'curve-style': 'bezier',
        'width': 'mapData(width, 1, 3, 1, 3)'
    }},
    {'selector': '[edge_type = "causal"]', 'style': {
        'line-color': '#333',
        'target-arrow-shape': 'triangle',
        'target-arrow-color': '#333'
    }},
    {'selector': '[edge_type = "participation"]', 'style': {
        'line-color': '#999',
        'line-style': 'dashed',
        'target-arrow-shape': 'tee',
        'target-arrow-color': '#999'
    }},
    {'selector': 'node:selected', 'style': {
        'border-width': 3,
        'border-color': 'black',
        'border-opacity': 1,
        'opacity': 1
    }},
    {'selector': 'edge:selected', 'style': {
        'width': 4,
        'line-color': 'black',
        'opacity': 1
    }}
]

def create_cytoscape_elements(view_option='full', search_text=""):
    """
    Generate Cytoscape elements based on the view option and search filter.
    """
    if debug_mode:
        print(f"Creating Cytoscape elements with view_option={view_option}, search_text='{search_text}'")
    
    # Start with full set (all_nodes + all_edges)
    filtered_nodes = all_nodes.copy()
    filtered_edges = all_edges.copy()
    
    # If a search text is provided, filter nodes whose label (case-insensitive) contains the search string.
    if search_text:
        search_text_lower = search_text.lower()
        filtered_nodes = [node for node in all_nodes if search_text_lower in node['label'].lower()]
        filtered_ids = {node['id'] for node in filtered_nodes}
        # Also include any edge that connects to these nodes
        filtered_edges = [edge for edge in all_edges if edge['source'] in filtered_ids or edge['target'] in filtered_ids]
    
    # If view_option is set to filter by type (e.g., 'events', 'actors', 'russia', 'international')
    # then further filter the nodes/edges.
    node_ids_in_view = set(n['id'] for n in filtered_nodes)
    if view_option == 'events':
        filtered_nodes = [n for n in filtered_nodes if n['type'] == "Event"]
        node_ids_in_view = set(n['id'] for n in filtered_nodes)
        filtered_edges = [e for e in filtered_edges if e['source'] in node_ids_in_view and e['target'] in node_ids_in_view]
    elif view_option == 'actors':
        actor_related = [n for n in filtered_nodes if n['type'] in ["Actor", "Individual"]]
        actor_ids = {n['id'] for n in actor_related}
        # Include events that are linked to these actors via participation edges
        linked_events = set()
        for edge in actor_event_edges + individual_event_edges:
            if edge['source'] in actor_ids:
                linked_events.add(edge['target'])
            if edge['target'] in actor_ids:
                linked_events.add(edge['source'])
        event_subset = [n for n in all_nodes if n['type'] == "Event" and n['id'] in linked_events]
        filtered_nodes = actor_related + event_subset
        node_ids_in_view = {n['id'] for n in filtered_nodes}
        filtered_edges = [e for e in all_edges if e['source'] in node_ids_in_view and e['target'] in node_ids_in_view]
    elif view_option == 'russia':
        russia_focus = { "Russia (Russian Federation)", "Vladimir Putin", "Sergey Aksyonov", "Crimean Supreme Council (Parliament)", "Russian Armed Forces (Black Sea Fleet)", "Crimean 'Self-Defense' Forces", "Russian Federation Council", "Russian State Duma & Federation Council", "Russian Parliament", "Unmarked Russian special forces", "Crimean gov't (Aksyonov)", "Aleksei Chaly", "Russian Unity party", "Russian gov't" }
        node_ids_in_view = set(russia_focus)
        linked_events = set()
        for edge in all_edges:
            if edge['source'] in node_ids_in_view or edge['target'] in node_ids_in_view:
                node_ids_in_view.add(edge['source'])
                node_ids_in_view.add(edge['target'])
        filtered_nodes = [n for n in all_nodes if n['id'] in node_ids_in_view]
        filtered_edges = [e for e in all_edges if e['source'] in node_ids_in_view and e['target'] in node_ids_in_view]
    elif view_option == 'international':
        intl_focus = { "United States", "European Union (EU) and G7", "United Nations", "NATO (North Atlantic Treaty Organization)", "OSCE (Organization for Security & Co-operation in Europe)", "Barack Obama", "G7 (USA, UK, France, Germany, Italy, Canada, Japan) & EU", "UN General Assembly (193 member states)", "United Nations Security Council (P5: Russia, US, UK, France, China)", "USA", "EU" }
        node_ids_in_view = set(intl_focus)
        linked_events = set()
        for edge in all_edges:
            if edge['source'] in node_ids_in_view or edge['target'] in node_ids_in_view:
                node_ids_in_view.add(edge['source'])
                node_ids_in_view.add(edge['target'])
        filtered_nodes = [n for n in all_nodes if n['id'] in node_ids_in_view]
        filtered_edges = [e for e in all_edges if e['source'] in node_ids_in_view and e['target'] in node_ids_in_view]
    
    # Build Cytoscape elements from nodes and edges.
    elements = []
    for node in filtered_nodes:
        # Build a JSON string of all node attributes (except id, label, color) for tooltip purposes.
        details = {k: v for k, v in node.items() if k not in ['id', 'label', 'color']}
        node_data = {
            'id': node['id'],
            'label': node['label'],
            'type': node['type'],
            'size': 25 if node['type'] == 'Event' else (15 if node['type'] == 'Individual' else 20),
            'details': json.dumps(details)
        }
        # Determine class for styling (based on type)
        node_class = node['type']  # "Event", "Actor", "Individual", etc.
        elements.append({'data': node_data, 'classes': node_class})
    for edge in filtered_edges:
        elements.append({
            'data': {
                'source': edge['source'],
                'target': edge['target'],
                'label': edge.get('label', ''),
                'width': 2 if edge['type'] == 'causal' else 1,
                'edge_type': edge['type']
            },
            'classes': edge['type']
        })
    
    if debug_mode:
        print(f"Created {len(elements)} Cytoscape elements ({len(filtered_nodes)} nodes, {len(filtered_edges)} edges)")
    
    return elements

# ------------------------------------------------------------------------------
# Create Plotly timeline figure using add_shape for key dates
# ------------------------------------------------------------------------------
def create_timeline_figure(filtered_df=timeline_df):
    """
    Generates the Plotly timeline figure.
    Uses px.timeline and adds key date markers using fig.add_shape.
    Includes timing prints for debugging performance.
    """
    start_time = datetime.now()
    func_name = "create_timeline_figure"
    if debug_mode:
        print(f"FUNC START: {func_name} at {start_time} with {len(filtered_df)} events")

    if filtered_df.empty:
        if debug_mode: print(f"FUNC END: {func_name} - No data.")
        fig = go.Figure()
        fig.update_layout(title="No events match filters.", height=600, xaxis={'visible': False}, yaxis={'visible': False})
        return fig

    # Ensure 'date_parsed' is datetime
    try:
        filtered_df['date_parsed'] = pd.to_datetime(filtered_df['date_parsed'])
        # Create dummy end date required by px.timeline
        filtered_df['end_date'] = filtered_df['date_parsed'] + pd.Timedelta(hours=12)
    except Exception as e:
        print(f"ERROR in {func_name}: Failed to process date columns - {e}")
        traceback.print_exc()
        fig = go.Figure()
        fig.add_annotation(text=f"Error processing date data: {e}", showarrow=False)
        return fig.update_layout(height=600)

    # --- Create the main timeline plot ---
    try:
        fig = px.timeline(
            filtered_df,
            x_start='date_parsed',
            x_end='end_date',
            y='type',
            color='type',
            hover_name='title',
            # Slightly simplified hover data - remove summary temporarily for performance test
            hover_data={'date': True, 'location': True, 'actors_str': True, #'summary': True,
                        'date_parsed': False, 'end_date': False, 'type': False},
            labels={"date_parsed": "Date", "type": "Event Type"},
            title="Chronology of Crimea Annexation Events",
            color_discrete_sequence=px.colors.qualitative.Plotly
        )
    except Exception as e:
        print(f"ERROR in {func_name}: px.timeline failed - {e}")
        traceback.print_exc()
        fig = go.Figure()
        fig.add_annotation(text=f"Error creating timeline plot: {e}", showarrow=False)
        return fig.update_layout(height=600)

    # --- Prepare Key Date Markers (Shapes and Annotations) ---
    key_dates = [
        {"date": "2014-02-27", "label": "Parliament Seized"},
        {"date": "2014-03-16", "label": "Referendum"},
        {"date": "2014-03-18", "label": "Annexation"},
        {"date": "2014-03-27", "label": "UN Vote"}
    ]
    shapes = []
    annotations = []

    # Calculate overall range ONCE using the original full timeline_df
    # Add buffer to min/max dates
    try:
        min_vis_date = timeline_df['date_parsed'].min() - pd.Timedelta(days=2)
        max_vis_date = timeline_df['date_parsed'].max() + pd.Timedelta(days=2)
    except Exception as e:
         print(f"ERROR in {func_name}: Cannot calculate date range from timeline_df - {e}")
         min_vis_date = pd.Timestamp('2013-11-01') # Fallback range
         max_vis_date = pd.Timestamp('2014-07-01') # Fallback range


    for kd in key_dates:
        try:
            # Use pd.Timestamp for consistency
            ts = pd.Timestamp(kd["date"])
            # Check if the key date falls within the calculated visible range
            if min_vis_date <= ts <= max_vis_date:
                # Shape dictionary for the vertical line
                shapes.append(dict(
                    type="line", xref="x", yref="paper", # x uses data, y uses paper (0 to 1)
                    x0=ts, y0=0, x1=ts, y1=1,           # Define the line coordinates
                    line=dict(color="grey", width=1, dash="dash")
                ))
                # Annotation dictionary for the label
                annotations.append(dict(
                    x=ts, y=1.05, # Position slightly above the plot area
                    yref="paper", # Relative to plot area height
                    showarrow=False,
                    text=kd["label"],
                    font=dict(size=10), # Adjusted font size
                    align="center"
                ))
        except Exception as e:
            # Log error for specific key date but continue processing others
            print(f"Error processing key date {kd['date']} for timeline markers: {e}")

    # --- Update Figure Layout ---
    try:
        fig.update_layout(
            shapes=shapes,           # Add the vertical line shapes
            annotations=annotations, # Add the labels
            xaxis_type='date',       # Ensure x-axis is treated as date
            xaxis=dict(              # Configure x-axis
                tickformat="%d %b %Y", # Date format
                title_text="Date",
                range=[min_vis_date, max_vis_date] # Set explicit range
            ),
            yaxis=dict(              # Configure y-axis (optional clarity)
                title_text="Event Type"
            ),
            height=600,
            margin=dict(l=20, r=20, t=50, b=20), # Standard margins
            title_x=0.5,             # Center title
            title_font_size=20,
            hoverlabel=dict(bgcolor="white", font_size=12, namelength=-1), # Hover style
            legend_title_text='Event Types' # Legend title
        )
    except Exception as e:
        print(f"ERROR in {func_name}: fig.update_layout failed - {e}")
        traceback.print_exc()
        # Attempt to return the figure without layout updates if update fails
        # fig.add_annotation(text=f"Layout update error: {e}", showarrow=False) # Add error to fig

    end_time = datetime.now()
    if debug_mode:
        print(f"FUNC END: {func_name} at {end_time}. Duration: {end_time - start_time}")
    return fig

# ------------------------------------------------------------------------------
# Actor Relationships Network (Plotly) and Actors Table functions
# ------------------------------------------------------------------------------
def create_actor_relationships():
    """Generates the Plotly network graph for actor relationships."""
    if debug_mode:
        print("Creating actor relationships network")

    # Simplified function that's guaranteed to return a valid figure
    try:
        # First try a simplified version that just shows key actors
        fig = go.Figure()
        
        # Use the top 10 actors for a simple demo graph
        top_actors = [a['name'] for a in actors[:5]] + [i['name'] for i in individuals[:5]]
        x_positions = [0, 2, 4, 6, 8, 1, 3, 5, 7, 9]
        y_positions = [5, 5, 5, 5, 5, 2, 2, 2, 2, 2]
        
        # Create simple node trace
        node_trace = go.Scatter(
            x=x_positions, 
            y=y_positions,
            mode='markers+text',
            text=top_actors,
            textposition="top center",
            marker=dict(
                size=20,
                color=['#FBBC05', '#FBBC05', '#4285F4', '#4285F4', '#34A853', 
                       '#8F44AD', '#8F44AD', '#8F44AD', '#8F44AD', '#8F44AD'],
                line=dict(width=1, color='black')
            ),
            hoverinfo='text',
            hovertext=top_actors
        )
        
        # Add edges between related nodes
        edge_x, edge_y = [], []
        # Just create some sample edges
        edges = [(0,5), (0,6), (1,7), (2,8), (3,9), (4,5), (0,1), (2,3)]
        for edge in edges:
            x0, y0 = x_positions[edge[0]], y_positions[edge[0]]
            x1, y1 = x_positions[edge[1]], y_positions[edge[1]]
            edge_x.extend([x0, x1, None])
            edge_y.extend([y0, y1, None])
            
        edge_trace = go.Scatter(
            x=edge_x, y=edge_y,
            line=dict(width=1, color='#888'),
            hoverinfo='none',
            mode='lines'
        )
        
        # Create figure
        fig.add_trace(edge_trace)
        fig.add_trace(node_trace)
        
        fig.update_layout(
            title='Actor Relationships (Simplified Demo)',
            title_font_size=16,
            showlegend=False,
            hovermode='closest',
            margin=dict(b=20, l=5, r=5, t=40),
            xaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
            yaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
            height=700
        )
        
        # Try creating the real network
        G = nx.Graph()
        # Create nodes for actors and individuals
        actor_node_data = {actor['name']: {'type': 'Actor', 'group': 1, 'color': node_types.get(actor['type'].split(' ')[0], node_types['Actor'])} for _, actor in actors_df.iterrows()}
        individual_node_data = {ind['name']: {'type': 'Individual', 'group': 2, 'color': node_types['Individual']} for _, ind in individuals_df.iterrows()}
        all_node_data = {**actor_node_data, **individual_node_data}
        for name, data in all_node_data.items():
            G.add_node(name, size=20 if data['type'] == 'Actor' else 15, type=data['type'], color=data['color'])
        # Add edges based on shared events from participation edges
        event_participants = {}
        for edge in actor_event_edges + individual_event_edges:
            event = edge['target']
            actor = edge['source']
            event_participants.setdefault(event, []).append(actor)
        for event, participants in event_participants.items():
            unique_participants = list(set(participants))
            for i in range(len(unique_participants)):
                for j in range(i + 1, len(unique_participants)):
                    u, v = unique_participants[i], unique_participants[j]
                    if G.has_edge(u, v):
                        G[u][v]['weight'] += 1
                        G[u][v].setdefault('events', []).append(event)
                    else:
                        G.add_edge(u, v, weight=1, events=[event])
        if not G.nodes():
            return fig  # Return the simple figure if no nodes in the real graph
        try:
            pos = nx.kamada_kawai_layout(G)
        except nx.NetworkXError:
            pos = nx.spring_layout(G, k=0.5, iterations=50)
        edge_x, edge_y, edge_hovertexts = [], [], []
        for edge in G.edges(data=True):
            x0, y0 = pos[edge[0]]
            x1, y1 = pos[edge[1]]
            edge_x.extend([x0, x1, None])
            edge_y.extend([y0, y1, None])
            weight = edge[2].get('weight', 1)
            events_common = edge[2].get('events', [])
            hover_text = f"{edge[0]} - {edge[1]}<br>Shared Events: {weight}<br>{'<br>'.join(events_common[:3])}{'... (more)' if len(events_common) > 3 else ''}"
            edge_hovertexts.extend([hover_text, hover_text, None])
        edge_trace = go.Scatter(x=edge_x, y=edge_y, line=dict(width=0.5, color='#888'),
                                hoverinfo='text', text=edge_hovertexts, mode='lines')
        node_x, node_y, node_text, node_color, node_size = [], [], [], [], []
        for node in G.nodes():
            x, y = pos[node]
            node_x.append(x)
            node_y.append(y)
            node_text.append(f"<b>{node}</b><br>Type: {G.nodes[node]['type']}")
            node_color.append(G.nodes[node]['color'])
            node_size.append(G.nodes[node]['size'])
        node_trace = go.Scatter(x=node_x, y=node_y, mode='markers+text', text=[name for name in G.nodes()],
                                textposition='top center', textfont=dict(size=9), hoverinfo='text',
                                hovertext=node_text,
                                marker=dict(showscale=False, color=node_color, size=node_size, line_width=1, line_color='black'))
        fig = go.Figure(data=[edge_trace, node_trace],
                 layout=go.Layout(
                    title='Actor Relationships Network (Based on Shared Events)',
                    title_font_size=16, # <<< CORRECTED PROPERTY NAME
                    showlegend=False,
                    hovermode='closest',
                                         margin=dict(b=20, l=5, r=5, t=40),
                                         xaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
                                         yaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
                                         height=700))
        return fig
    except Exception as e:
        if debug_mode:
            print(f"Error creating actor relationships network: {e}")
            traceback.print_exc()
        # Return a dummy figure with error message
        fig = go.Figure()
        fig.add_annotation(text=f"Error creating network graph: {str(e)}", showarrow=False)
        fig.update_layout(height=700)
        return fig

def create_actors_table():
    """Generates a DataFrame for the actors table."""
    try:
        table_data = []
        actor_event_map = {actor['name']: actor.get('events', []) for _, actor in actors_df.iterrows()}
        individual_event_map = {ind['name']: ind.get('events', []) for _, ind in individuals_df.iterrows()}
        for _, actor in actors_df.iterrows():
            events_involved = actor_event_map.get(actor['name'], [])
            table_data.append({
                'Name': actor['name'],
                'Type': actor['type'],
                'Role/Description': actor['role'],
                'Events Involved In': ', '.join(events_involved) if events_involved else 'None'
            })
        for _, individual in individuals_df.iterrows():
            events_involved = individual_event_map.get(individual['name'], [])
            table_data.append({
                'Name': individual['name'],
                'Type': f"Individual ({individual['role']})",
                'Role/Description': individual['description'],
                'Events Involved In': ', '.join(events_involved) if events_involved else 'None'
            })
        return pd.DataFrame(table_data)
    except Exception as e:
        if debug_mode:
            print(f"Error creating actors table: {e}")
            traceback.print_exc()
        # Return empty dataframe with correct columns
        return pd.DataFrame(columns=['Name', 'Type', 'Role/Description', 'Events Involved In'])

# ------------------------------------------------------------------------------
# DASH APP LAYOUT
# ------------------------------------------------------------------------------
app.layout = dbc.Container([
    dbc.Row([
        dbc.Col([
            html.H1("Crimea Annexation (2014): Interactive Analysis",
                    style={'textAlign': 'center', 'marginTop': '20px', 'marginBottom': '20px'}),
            html.P("A comprehensive visualization based on the FARO ontology.",
                   style={'textAlign': 'center', 'fontSize': '18px', 'marginBottom': '30px'})
        ], width=12)
    ]),

    dbc.Tabs([
        # ==============================================================
        # TAB 1: FARO Knowledge Graph (Cytoscape)
        # ==============================================================
        dbc.Tab(label="FARO Knowledge Graph", tab_id="tab-1", children=[
            dbc.Row([
                dbc.Col([
                    html.H3("FARO Ontology Network (Cytoscape)",
                            style={'textAlign': 'center', 'marginTop': '20px'}),
                    html.P("Interactive network. Pan/zoom, hover nodes/edges, click nodes for subgraph.",
                           style={'textAlign': 'center', 'marginBottom': '20px'})
                ], width=12)
            ]),
            # Controls Row
            dbc.Row([
                dbc.Col([
                    html.Label("Select Layout:", style={'fontWeight': 'bold'}),
                    dcc.Dropdown(
                        id='cytoscape-layout-dropdown',
                        options=[
                            {'label': 'Cose (Force Directed)', 'value': 'cose'},
                            {'label': 'Grid', 'value': 'grid'},
                            {'label': 'Circle', 'value': 'circle'},
                            {'label': 'Breadthfirst', 'value': 'breadthfirst'},
                            {'label': 'Dagre (Hierarchical)', 'value': 'dagre'}
                            # Add other layouts like 'cola' if dash-cytoscape version supports them
                        ],
                        value='cose', # <<< DEFAULT LAYOUT SET TO COSE
                        clearable=False
                    )
                ], width=6, md=4),
                dbc.Col([
                    html.Label("Search Nodes:", style={'fontWeight': 'bold'}),
                    dcc.Input(id="cytoscape-search-input", type="text", placeholder="Filter nodes by label...", debounce=True, style={"width": "100%"})
                ], width=6, md=4),
                 dbc.Col([
                     # Add vertical space using margin
                     html.Button("Reset/Refilter", id="reset-btn", n_clicks=0, className="btn btn-secondary w-100", style={"marginTop": "31px"})
                 ], width=12, md=3, className="mt-3 mt-md-0 d-flex align-items-end") # Align button bottom on medium+ screens
            ], justify="center", style={'marginBottom': '20px'}),

            # Cytoscape Graph Row
            dbc.Row([
                dbc.Col([
                    html.Div(id="cytoscape-loading-output", children="", style={'textAlign': 'center', 'marginBottom': '5px', 'fontStyle': 'italic', 'color': 'grey'}),
                    dcc.Loading(id="loading-cytoscape", type="circle", children=[
                        cyto.Cytoscape(
                            id='cytoscape-faro-network',
                            elements=create_cytoscape_elements('full'), # Initial load: full graph
                            layout={'name': 'cose', 'animate': False}, # <<< INITIAL LAYOUT SET TO COSE
                            style={'width': '100%', 'height': '750px', 'border': '1px solid #ddd', 'backgroundColor': '#f9f9f9'},
                            stylesheet=default_stylesheet,
                            # Performance options
                            minZoom=0.1,
                            maxZoom=2.0
                        )
                    ], fullscreen=False)
                ], width=12)
            ]),

            # Info Display Row
            dbc.Row([
                 dbc.Col([
                    html.H5("Hover Details:", style={'marginTop': '15px'}),
                    html.Div(id='cytoscape-hover-output', style={'padding': '10px', 'border': '1px solid #eee', 'minHeight': '60px', 'fontSize': '14px'}, children="Hover over a node or edge.")
                 ], md=6),
                 dbc.Col([
                    html.H5("Click Details:", style={'marginTop': '15px'}),
                    html.Div(id='cytoscape-tapNodeData-output', style={'padding': '10px', 'border': '1px dashed #ccc', 'minHeight': '60px', 'fontSize': '14px', 'maxHeight': '200px', 'overflowY':'auto'}, children="Click on a node to see subgraph info.")
                 ], md=6)
            ]),

            # Legend Row
            dbc.Row([
                 dbc.Col([
                    html.Div([
                         html.H5("Legend:", style={'marginTop':'15px'}),
                         dbc.Row([
                             dbc.Col([
                                 html.Div([html.Div(style={'backgroundColor': node_types["Event"], 'width': '18px', 'height': '18px', 'display': 'inline-block', 'marginRight': '5px', 'border': '1px solid #ccc', 'borderRadius': '50%'}), html.Span(" Event", style={'verticalAlign': 'middle'})], style={'marginBottom': '5px'}),
                                 html.Div([html.Div(style={'backgroundColor': node_types["Individual"], 'width': '18px', 'height': '18px', 'display': 'inline-block', 'marginRight': '5px', 'border': '1px solid #ccc', 'transform': 'rotate(45deg)'}), html.Span(" Individual", style={'verticalAlign': 'middle'})], style={'marginBottom': '5px'}),
                             ], width=6, sm=3),
                             dbc.Col([
                                 html.Div([html.Div(style={'backgroundColor': node_types["Country"], 'width': '18px', 'height': '18px', 'display': 'inline-block', 'marginRight': '5px', 'border': '1px solid #ccc'}), html.Span(" Country", style={'verticalAlign': 'middle'})], style={'marginBottom': '5px'}),
                                 html.Div([html.Div(style={'backgroundColor': node_types["Organization"], 'width': '18px', 'height': '18px', 'display': 'inline-block', 'marginRight': '5px', 'border': '1px solid #ccc'}), html.Span(" Organization", style={'verticalAlign': 'middle'})], style={'marginBottom': '5px'}),
                             ], width=6, sm=3),
                              dbc.Col([
                                 html.Div([html.Div(style={'backgroundColor': node_types["Actor"], 'width': '18px', 'height': '18px', 'display': 'inline-block', 'marginRight': '5px', 'border': '1px solid #ccc'}), html.Span(" Other Actor", style={'verticalAlign': 'middle'})], style={'marginBottom': '5px'}),
                             ], width=6, sm=3),
                              dbc.Col([
                                 html.Div([html.Span(style={'borderTop': '2px solid #333', 'display':'inline-block', 'width':'20px', 'marginRight':'5px'}), html.Span(" Causal Link", style={'verticalAlign': 'middle'})], style={'marginBottom': '5px'}),
                                 html.Div([html.Span(style={'borderTop': '1px dashed #999', 'display':'inline-block', 'width':'20px', 'marginRight':'5px'}), html.Span(" Participation Link", style={'verticalAlign': 'middle'})], style={'marginBottom': '5px'}),
                             ], width=6, sm=3)
                         ], justify="start")
                    ], style={'marginTop': '10px', 'padding': '10px', 'border': '1px solid #ddd', 'backgroundColor': 'rgba(250, 250, 250, 0.9)', 'fontSize': '13px'})
                 ], width=12)
            ]),

        ], tab_id="tab-1"), # End of Tab 1# ------------------------------------------------------------------------------
# DASH APP LAYOUT
# ------------------------------------------------------------------------------
app.layout = dbc.Container([
    # ================== Header Row ==================
    dbc.Row([
        dbc.Col([
            html.H1("Crimea Annexation (2014): Interactive Analysis",
                    style={'textAlign': 'center', 'marginTop': '20px', 'marginBottom': '20px'}),
            html.P("A comprehensive visualization based on the FARO ontology.",
                   style={'textAlign': 'center', 'fontSize': '18px', 'marginBottom': '30px'})
        ], width=12)
    ]), # End Header Row

    # ================== Main Tabs ==================
    dbc.Tabs([
        # ==============================================================
        # TAB 1: FARO Knowledge Graph (Cytoscape)
        # ==============================================================
        dbc.Tab(label="FARO Knowledge Graph", tab_id="tab-1", children=[
            dbc.Row([ # Header Row for Tab 1
                dbc.Col([
                    html.H3("FARO Ontology Network (Cytoscape)", style={'textAlign': 'center', 'marginTop': '20px'}),
                    html.P("Interactive network. Pan/zoom, hover nodes/edges, click nodes for subgraph.", style={'textAlign': 'center', 'marginBottom': '20px'})
                ], width=12)
            ]), # End Header Row Tab 1

            # Controls Row for Tab 1
            dbc.Row([
                dbc.Col([
                    html.Label("Select Layout:", style={'fontWeight': 'bold'}),
                    dcc.Dropdown(
                        id='cytoscape-layout-dropdown',
                        options=[
                            {'label': 'Cose (Force Directed)', 'value': 'cose'},
                            {'label': 'Grid', 'value': 'grid'},
                            {'label': 'Circle', 'value': 'circle'},
                            {'label': 'Breadthfirst', 'value': 'breadthfirst'},
                            {'label': 'Dagre (Hierarchical)', 'value': 'dagre'}
                        ],
                        value='cose', # Default layout set to cose
                        clearable=False
                    )
                ], width=6, md=4),
                dbc.Col([
                    html.Label("Search Nodes:", style={'fontWeight': 'bold'}),
                    dcc.Input(id="cytoscape-search-input", type="text", placeholder="Filter nodes by label...", debounce=True, style={"width": "100%"})
                ], width=6, md=4),
                 dbc.Col([
                     html.Button("Reset/Refilter", id="reset-btn", n_clicks=0, className="btn btn-secondary w-100", style={"marginTop": "31px"})
                 ], width=12, md=3, className="mt-3 mt-md-0 d-flex align-items-end")
            ], justify="center", style={'marginBottom': '20px'}), # End Controls Row Tab 1

            # Cytoscape Graph Row for Tab 1
            dbc.Row([
                dbc.Col([
                    html.Div(id="cytoscape-loading-output", children="", style={'textAlign': 'center', 'marginBottom': '5px', 'fontStyle': 'italic', 'color': 'grey'}),
                    dcc.Loading(id="loading-cytoscape", type="circle", children=[
                        cyto.Cytoscape(
                            id='cytoscape-faro-network',
                            elements=create_cytoscape_elements('full'), # Initial load: full graph
                            layout={'name': 'cose', 'animate': False, 'idealEdgeLength': 100, 'nodeRepulsion': 400000}, # Initial layout set to cose
                            style={'width': '100%', 'height': '750px', 'border': '1px solid #ddd', 'backgroundColor': '#f9f9f9'},
                            stylesheet=default_stylesheet,
                            minZoom=0.1, maxZoom=2.0
                        )
                    ], fullscreen=False)
                ], width=12)
            ]), # End Cytoscape Graph Row Tab 1

            # Info Display Row for Tab 1
            dbc.Row([
                 dbc.Col([
                    html.H5("Hover Details:", style={'marginTop': '15px'}),
                    html.Div(id='cytoscape-hover-output', style={'padding': '10px', 'border': '1px solid #eee', 'minHeight': '60px', 'fontSize': '14px'}, children="Hover over a node or edge.")
                 ], md=6),
                 dbc.Col([
                    html.H5("Click Details:", style={'marginTop': '15px'}),
                    html.Div(id='cytoscape-tapNodeData-output', style={'padding': '10px', 'border': '1px dashed #ccc', 'minHeight': '60px', 'fontSize': '14px', 'maxHeight': '200px', 'overflowY':'auto'}, children="Click on a node to see subgraph info.")
                 ], md=6)
            ]), # End Info Display Row Tab 1

            # Legend Row for Tab 1
            dbc.Row([
                 dbc.Col([
                    html.Div([
                         html.H5("Legend:", style={'marginTop':'15px'}),
                         dbc.Row([
                             dbc.Col([
                                 html.Div([html.Div(style={'backgroundColor': node_types["Event"], 'width': '18px', 'height': '18px', 'display': 'inline-block', 'marginRight': '5px', 'border': '1px solid #ccc', 'borderRadius': '50%'}), html.Span(" Event", style={'verticalAlign': 'middle'})], style={'marginBottom': '5px'}),
                                 html.Div([html.Div(style={'backgroundColor': node_types["Individual"], 'width': '18px', 'height': '18px', 'display': 'inline-block', 'marginRight': '5px', 'border': '1px solid #ccc', 'transform': 'rotate(45deg)'}), html.Span(" Individual", style={'verticalAlign': 'middle'})], style={'marginBottom': '5px'}),
                             ], width=6, sm=3),
                             dbc.Col([
                                 html.Div([html.Div(style={'backgroundColor': node_types["Country"], 'width': '18px', 'height': '18px', 'display': 'inline-block', 'marginRight': '5px', 'border': '1px solid #ccc'}), html.Span(" Country", style={'verticalAlign': 'middle'})], style={'marginBottom': '5px'}),
                                 html.Div([html.Div(style={'backgroundColor': node_types["Organization"], 'width': '18px', 'height': '18px', 'display': 'inline-block', 'marginRight': '5px', 'border': '1px solid #ccc'}), html.Span(" Organization", style={'verticalAlign': 'middle'})], style={'marginBottom': '5px'}),
                             ], width=6, sm=3),
                              dbc.Col([
                                 html.Div([html.Div(style={'backgroundColor': node_types["Actor"], 'width': '18px', 'height': '18px', 'display': 'inline-block', 'marginRight': '5px', 'border': '1px solid #ccc'}), html.Span(" Other Actor", style={'verticalAlign': 'middle'})], style={'marginBottom': '5px'}),
                             ], width=6, sm=3),
                              dbc.Col([
                                 html.Div([html.Span(style={'borderTop': '2px solid #333', 'display':'inline-block', 'width':'20px', 'marginRight':'5px'}), html.Span(" Causal Link", style={'verticalAlign': 'middle'})], style={'marginBottom': '5px'}),
                                 html.Div([html.Span(style={'borderTop': '1px dashed #999', 'display':'inline-block', 'width':'20px', 'marginRight':'5px'}), html.Span(" Participation Link", style={'verticalAlign': 'middle'})], style={'marginBottom': '5px'}),
                             ], width=6, sm=3)
                         ], justify="start")
                    ], style={'marginTop': '10px', 'padding': '10px', 'border': '1px solid #ddd', 'backgroundColor': 'rgba(250, 250, 250, 0.9)', 'fontSize': '13px'})
                 ], width=12)
            ]), # End Legend Row Tab 1

        ]), # <<< End of Tab 1 Definition

        # ==============================================================
        # TAB 2: Chronological Event Timeline
        # ==============================================================
        dbc.Tab(label="Chronological Event Timeline", tab_id="tab-2", children=[
            dbc.Row([ # Header Row Tab 2
                dbc.Col([
                    html.H3("Timeline of Key Events", style={'textAlign': 'center', 'marginTop': '20px'}),
                    html.P("Use the dropdown below to filter by event type and the date picker for a custom range.", style={'textAlign': 'center', 'marginBottom': '20px'})
                ], width=12)
            ]), # End Header Row Tab 2
            dbc.Row([ # Filters Row Tab 2
                dbc.Col([
                    html.Label("Filter by Event Type:", style={'fontWeight': 'bold'}),
                    dcc.Dropdown(
                        id='event-type-dropdown',
                        options=[{'label': t, 'value': t} for t in sorted(timeline_df['type'].unique())],
                        value=[], multi=True, placeholder="Select event types..."
                    )
                ], width=12, md=6),
                dbc.Col([
                    html.Label("Date Range:", style={'fontWeight': 'bold'}),
                    dcc.DatePickerRange(
                        id='date-range-picker',
                        min_date_allowed=timeline_df['date_parsed'].min().date(),
                        max_date_allowed=timeline_df['date_parsed'].max().date(),
                        start_date=timeline_df['date_parsed'].min().date(),
                        end_date=timeline_df['date_parsed'].max().date(),
                        display_format='DD MMM YY'
                    )
                ], width=12, md=6)
            ], justify="center", style={'marginBottom': '20px'}), # End Filters Row Tab 2
            dbc.Row([ # Timeline Graph Row Tab 2
                dbc.Col([
                    html.Div(id="timeline-loading-output", children="", style={'textAlign': 'center', 'marginBottom': '5px', 'fontStyle': 'italic', 'color': 'grey'}),
                    dcc.Loading(id='loading-timeline', type='circle', children=[
                        dcc.Graph(id='timeline-graph', figure=create_timeline_figure(), style={'height': '600px'})
                    ])
                ], width=12)
            ]), # End Timeline Graph Row Tab 2
            dbc.Row([ # Event Details Row Tab 2
                dbc.Col([
                    html.H4("Event Details", style={'marginTop': '30px'}),
                    dcc.Loading(id='loading-event-details', type='circle', children=[
                        html.Div(id='event-details', children="Click on an event in the timeline above to see details.", style={'padding': '15px', 'border': '1px solid #eee', 'minHeight': '100px', 'marginTop':'10px'})
                    ])
                ], width=12)
            ]) # End Event Details Row Tab 2
        ]), # <<< End of Tab 2 Definition

        # ==============================================================
        # TAB 3: Actors and Roles
        # ==============================================================
        dbc.Tab(label="Actors and Roles", tab_id="tab-3", children=[
             dbc.Row([ # Header Row Tab 3
                dbc.Col([
                    html.H3("Key Actors", style={'textAlign': 'center', 'marginTop': '20px'}),
                    html.P("Toggle between the relationship network and a detailed table.", style={'textAlign': 'center', 'marginBottom': '20px'})
                ], width=12)
             ]), # End Header Row Tab 3
             dbc.Row([ # Toggle Row Tab 3
                 dbc.Col(
                     dbc.RadioItems(
                        id='actor-view-toggle',
                        options=[{'label': 'Relationship Network', 'value': 'network'}, {'label': 'Detailed Table', 'value': 'table'}],
                        value='network', inline=True, className="d-flex justify-content-center"
                     ), width=12, style={'marginBottom': '20px'}
                 )
             ]), # End Toggle Row Tab 3
            dbc.Row([ # Content Row Tab 3
                dbc.Col([
                    # Network View Container
                    html.Div(id='actor-network-container', children=[
                        html.Div(id="actor-network-loading-output", children="", style={'textAlign': 'center', 'marginBottom': '5px', 'fontStyle': 'italic', 'color': 'grey'}),
                        dcc.Loading(id='loading-actor-network', type='circle', children=[
                            dcc.Graph(id='actor-network-graph', figure=create_actor_relationships(), style={'height': '700px'})
                        ])
                    ], style={'display': 'block'}), # Network initially visible

                    # Table View Container
                    html.Div(id='actor-table-container', children=[
                        html.Div(id="actor-table-loading-output", children="", style={'textAlign': 'center', 'marginBottom': '5px', 'fontStyle': 'italic', 'color': 'grey'}),
                        dash_table.DataTable(
                            id='actors-table',
                            columns=[ # Match columns with create_actors_table output
                                {'name': 'Name', 'id': 'Name'},
                                {'name': 'Type', 'id': 'Type'},
                                {'name': 'Role/Description', 'id': 'Role/Description'}, # Adjusted name
                                {'name': 'Events Involved In', 'id': 'Events Involved In'} # Adjusted name
                            ],
                            data=create_actors_table().to_dict('records'),
                            style_table={'overflowX': 'auto'},
                            style_header={'backgroundColor': 'rgb(230, 230, 230)', 'fontWeight': 'bold'},
                            style_cell={'textAlign': 'left', 'padding': '10px', 'whiteSpace': 'normal', 'height': 'auto', 'minWidth': '100px', 'width': 'auto', 'maxWidth': '300px'},
                            page_size=15, filter_action="native", sort_action="native", sort_mode="multi",
                            style_data_conditional=[{'if': {'row_index': 'odd'}, 'backgroundColor': 'rgb(248, 248, 248)'}]
                        )
                    ], style={'display': 'none'}) # Table initially hidden
                ], width=12)
            ]), # End Content Row Tab 3
             dbc.Row([ # Actor Details Row Tab 3
                dbc.Col([
                    html.H4("Actor Details", style={'marginTop': '30px'}),
                    dcc.Loading(id='loading-actor-details', type='circle', children=[
                        html.Div(id='actor-details', children="Select an actor from the network or table above to view details.", style={'padding': '15px', 'border': '1px solid #eee', 'minHeight': '100px', 'marginTop':'10px'})
                    ])
                ], width=12)
            ]) # End Actor Details Row Tab 3
        ]), # <<< End of Tab 3 Definition

        # ==============================================================
        # TAB 4: Analysis & Perspectives
        # ==============================================================
        dbc.Tab(label="Analysis & Perspectives", tab_id="tab-4", children=[
            dbc.Row([ # Header Row Tab 4
                dbc.Col([
                     html.H3("Analysis of the Crimea Annexation", style={'textAlign': 'center', 'marginTop': '20px'}),
                     html.P("Key patterns and perspectives on the annexation.", style={'textAlign': 'center', 'marginBottom': '20px'}),
                ], width=12)
            ]), # End Header Row Tab 4

            # Analysis Sub-Tabs
            dbc.Tabs([
                 # --- Causal Patterns Sub-Tab (Uses Cytoscape) ---
                dbc.Tab(
                    label="Causal Patterns",
                    tab_id="analysis-causal",
                    children=[
                        dbc.Row([
                            dbc.Col([
                                html.H4("Causal Chain Analysis", style={'marginTop': '20px'}),
                                html.P("The annexation unfolded through a series of causal steps:"),
                                html.Ol([
                                    html.Li("Ukrainian Revolution triggers protests."),
                                    html.Li("Pro-Russian sentiment rises in Crimea."),
                                    html.Li("Covert Russian special forces seize key sites."),
                                    html.Li("Pro-Russian leadership is installed."),
                                    html.Li("A hastily organized referendum is held."),
                                    html.Li("Formal annexation follows."),
                                    html.Li("International condemnation and sanctions are imposed."),
                                    html.Li("Control is consolidated in Crimea.")
                                ]),
                                html.Div([
                                    html.H5("Causal Network Visualization", style={'marginTop':'25px'}),
                                    html.P("Shows direct causal links between key events. Arrows indicate relationship (e.g., 'Escalation', 'Pretext')."),
                                    dcc.Loading(id='loading-causal-cyto', type='circle', children=[
                                        cyto.Cytoscape(
                                            id='cytoscape-causal-graph',
                                            elements=create_cytoscape_elements('causal_only'), # Use the specific filter
                                            layout={'name': 'dagre', 'rankDir': 'LR', 'animate': True, 'spacingFactor': 1.2}, # Dagre Left->Right
                                            style={'width': '100%', 'height': '600px', 'border': '1px solid lightgrey'},
                                            stylesheet=default_stylesheet
                                        )
                                    ])
                                ])
                            ], width=12)
                        ])
                    ]
                ), # End of Causal Patterns sub-tab

                # --- International Response Sub-Tab (Plotly Graphs) ---
                dbc.Tab(
                    label="International Response",
                    tab_id="analysis-intl",
                    children=[
                        dbc.Row([
                            dbc.Col([
                                html.H4("International Response Analysis", style={'marginTop': '20px'}),
                                html.P("The international community responded with sanctions, diplomatic measures, and organizational actions."),
                                dbc.Row([
                                    dbc.Col([
                                        html.H5("UN General Assembly Vote (Res 68/262)"),
                                        dcc.Loading(id='loading-un-vote', type='circle', children=[
                                            dcc.Graph(
                                                id='un-vote-chart',
                                                figure=px.pie(names=['In favor (Affirming Ukraine Integrity)', 'Against (Opposing Resolution)', 'Abstentions', 'Non-Voting'], values=[100, 11, 58, 24], title="UNGA Vote on Ukraine's Territorial Integrity (Mar 2014)", color_discrete_sequence=['#4285F4', '#EA4335', '#FBBC05', '#CCCCCC'], hole=0.3).update_traces(textinfo='percent+label')
                                            )
                                        ])
                                    ], width=12, lg=6),
                                    dbc.Col([
                                        html.H5("Initial Sanctions Timeline (Mar-Jul 2014)"),
                                        dcc.Loading(id='loading-sanctions-timeline', type='circle', children=[
                                            dcc.Graph(
                                                id='sanctions-timeline',
                                                figure=px.timeline(
                                                    pd.DataFrame([ dict(Sanction="US Initial Individual Sanctions", Start='2014-03-17', Finish='2014-03-20', Actor='US'), dict(Sanction="EU Initial Individual Sanctions", Start='2014-03-17', Finish='2014-03-21', Actor='EU'), dict(Sanction="G7 Suspends Russia", Start='2014-03-24', Finish='2014-03-25', Actor='G7'), dict(Sanction="Expanded Sectoral Sanctions", Start='2014-07-16', Finish='2014-07-31', Actor='US/EU') ]),
                                                    x_start="Start", x_end="Finish", y="Sanction", color="Actor", title="Timeline of Early Western Sanctions", labels={"Sanction": "Sanction Type/Action"}
                                                ).update_yaxes(categoryorder='array', categoryarray=["Expanded Sectoral Sanctions", "G7 Suspends Russia", "EU Initial Individual Sanctions", "US Initial Individual Sanctions"])
                                            )
                                        ])
                                    ], width=12, lg=6)
                                ]),
                                html.H5("Key Response Patterns:", style={'marginTop': '30px'}),
                                html.Ul([ html.Li("Diplomatic condemnation and legal resolutions."), html.Li("Economic sanctions and asset freezes."), html.Li("Actions by international organizations."), html.Li("Avoidance of direct military confrontation."), html.Li("Long-term strategic isolation of Russia.") ])
                            ], width=12)
                        ])
                    ]
                ), # End of International Response sub-tab

                 # --- Legal & Territorial Sub-Tab (Text & Card) ---
                dbc.Tab(
                    label="Legal & Territorial Impact",
                    tab_id="analysis-legal",
                    children=[
                         dbc.Row([
                            dbc.Col([
                                html.H4("Legal and Territorial Consequences", style={'marginTop': '20px'}),
                                html.P("The annexation violated several international legal principles while permanently altering Crimea's status."),
                                dbc.Row([
                                    dbc.Col([
                                        html.H5("Violations of International Law Cited"),
                                        html.Ul([ html.Li([html.Strong("UN Charter:"), " Prohibition against the use of force to alter borders."]), html.Li([html.Strong("Helsinki Final Act (1975):"), " Inviolability of frontiers."]), html.Li([html.Strong("Budapest Memorandum (1994):"), " Pledges to respect Ukraine's sovereignty."]), html.Li([html.Strong("Russia-Ukraine Friendship Treaty (1997):"), " Explicit recognition of Crimea as part of Ukraine."]), html.Li([html.Strong("Ukrainian Constitution:"), " Requires national referendum for territorial changes."]) ]),
                                        html.H5("Russian Justifications / Counterarguments:", style={'marginTop': '15px'}),
                                        html.Ul([ html.Li("Protection of Russian speakers."), html.Li("Right to self-determination."), html.Li("Alleged invitation from a deposed leader."), html.Li("Correction of historical injustice.") ])
                                    ], width=12, lg=6),
                                    dbc.Col([
                                        html.H5("Territorial Impact - Crimea Profile"),
                                        dbc.Card( dbc.CardBody([ html.P([html.Strong("Area: "), "~27,000 km²"]), html.P([html.Strong("Population (2014 est.): "), "~2.3 million"]), html.P([html.Strong("Coastline: "), "~1,000 km"]), html.P([html.Strong("Strategic Importance: "), "Base for Russia's Black Sea Fleet"]), html.P([html.Strong("Economic Impact: "), "Loss of tourism, port revenue, and international trade."]) ]), className="mb-3" ),
                                        html.P( [html.Strong("Status Discrepancy:"), " Russia administers Crimea despite non-recognition by most nations."], style={'marginTop': '20px'} )
                                    ], width=12, lg=6)
                                ]),
                                html.P( [html.Strong("Lasting Status (as of April 2025):"), " Crimea remains under Russian control, with ongoing legal and diplomatic disputes."], style={'marginTop': '20px', 'fontWeight': 'bold'} )
                            ], width=12)
                        ])
                    ]
                ) # End of Legal & Territorial sub-tab
            ], id='analysis-subtabs', active_tab="analysis-causal") # End of inner Tabs
        ]), # <<< End of Tab 4 Definition

    ], id='tabs', active_tab="tab-1"), # End of Main Tabs Container

    # ================== Footer Row ==================
    dbc.Row([
        dbc.Col([
            html.Hr(),
            html.P(
                ["Data compiled from open sources.", html.Br(), "Visualization based on FARO ontology."],
                style={'textAlign': 'center', 'marginTop': '20px', 'color': '#666', 'fontSize': '14px'}
            )
        ], width=12)
    ]), # End Footer Row

    # ================== Debug Div ==================
    html.Div(id='debug-info', children="Debug info will appear here",
             style={'marginTop': '30px', 'padding': '15px', 'border': '1px solid #ccc',
                    'borderRadius': '5px', 'display': 'none' if not debug_mode else 'block'})

], fluid=True, style={'fontFamily': 'Arial, sans-serif'}) # End dbc.Container

# ------------------------------------------------------------------------------
# CALLBACKS - with additional error handling and debug output
# ------------------------------------------------------------------------------

# Callback for Cytoscape layout dropdown
@app.callback(
    [Output('cytoscape-faro-network', 'layout'),
     Output('cytoscape-loading-output', 'children')],
    Input('cytoscape-layout-dropdown', 'value')
)
def update_cytoscape_layout(layout_name):
    if debug_mode:
        print(f"Updating layout to: {layout_name}")
    
    try:
        layout_config = {'name': layout_name, 'animate': False}  # Disabled animation for better performance
        if layout_name == 'cose':
            layout_config['idealEdgeLength'] = 100
            layout_config['nodeRepulsion'] = 400000
        elif layout_name == 'dagre':
            layout_config['rankDir'] = 'TB'
        
        return layout_config, f"Graph displayed using {layout_name} layout. Click nodes to explore connections."
    except Exception as e:
        if debug_mode:
            print(f"Error updating layout: {e}")
        return {'name': 'grid'}, f"Error loading {layout_name} layout. Using grid instead."

# Callback for hover: show large tooltip on node or edge mouseover
@app.callback(
    Output('cytoscape-hover-output', 'children'),
    [Input('cytoscape-faro-network', 'mouseoverNodeData'),
     Input('cytoscape-faro-network', 'mouseoverEdgeData')]
)
def display_hover_data(node_data, edge_data):
    try:
        if node_data is not None:
            try:
                details = json.loads(node_data.get('details', '{}'))
                # Convert details to a more readable format
                formatted_details = []
                for key, value in details.items():
                    if key == 'summary' and isinstance(value, str) and len(value) > 100:
                        # Truncate long summaries
                        formatted_details.append(html.P([html.Strong(f"{key.title()}: "), value[:100] + "..."]))
                    elif isinstance(value, list):
                        formatted_details.append(html.P([html.Strong(f"{key.title()}: "), ", ".join(value)]))
                    else:
                        formatted_details.append(html.P([html.Strong(f"{key.title()}: "), str(value)]))
                
                content = [html.Strong(f"Node: {node_data.get('label', 'Unknown')}"), html.Br()] + formatted_details
                return content
            except json.JSONDecodeError:
                return [html.Strong("Node Details:"), html.Br(), html.P("Error parsing node details")]
        elif edge_data is not None:
            content = [
                html.Strong("Edge Details:"), 
                html.Br(), 
                html.P([html.Strong("Relationship: "), edge_data.get('label', 'Unknown')])
            ]
            return content
        return "Hover over a node or edge to see details."
    except Exception as e:
        if debug_mode:
            print(f"Error in hover display: {e}")
        return "Error displaying hover data."

# Callback to update Cytoscape elements based on node tap, reset button, and search input
@app.callback(
    [Output('cytoscape-faro-network', 'elements'),
     Output('cytoscape-tapNodeData-output', 'children'),
     Output('debug-info', 'children')],
    [Input('cytoscape-faro-network', 'tapNodeData'),
     Input('reset-btn', 'n_clicks'),
     Input('cytoscape-search-input', 'value')]
)
def filter_subgraph(tap_node, reset_clicks, search_value):
    """
    Updates Cytoscape elements based on interactions:
    - Node tap: Shows subgraph of tapped node and its neighbors.
    - Reset button: Shows the full graph (potentially filtered by search).
    - Search input: Filters the full graph based on the search text.
    """
    ctx = dash.callback_context
    debug_info = "Callback triggered. "

    # Determine which input triggered the callback
    if not ctx.triggered:
        trigger_id = 'initial_load'
        debug_info += "Initial load."
    else:
        trigger_id = ctx.triggered[0]['prop_id'].split('.')[0]
        debug_info += f"Trigger ID: {trigger_id}."

    try:
        # Handle Reset Button Click
        if trigger_id == "reset-btn" and reset_clicks > 0:
            debug_info += f" Reset button clicked ({reset_clicks}). Search value: '{search_value}'."
            # Reset shows full graph, filtered only by current search term
            elements = create_cytoscape_elements('full', search_text=search_value or "")
            tap_output_msg = "Graph reset."
            if search_value:
                 tap_output_msg += f" Showing search results for '{search_value}'."
            else:
                 tap_output_msg += " Click on a node to see its subgraph details."
            return elements, tap_output_msg, debug_info

        # Handle Search Input Change (including clearing the search)
        if trigger_id == "cytoscape-search-input":
            debug_info += f" Search input changed. Value: '{search_value}'."
            # Filter full graph based on search
            elements = create_cytoscape_elements('full', search_text=search_value or "")
            tap_output_msg = f"Showing search results for '{search_value}'." if search_value else "Search cleared. Click on a node..."
            return elements, tap_output_msg, debug_info

        # Handle Node Tap
        if trigger_id == "cytoscape-faro-network" and tap_node is not None:
            node_id = tap_node.get('id')
            node_label = tap_node.get('label', node_id) # Use label for message
            debug_info += f" Node tapped: {node_label}."

            # Get neighbors from all_edges (1-hop neighborhood)
            neighbors = {node_id} # Include the tapped node itself
            neighbor_details_list = [] # For descriptive output message

            for edge in all_edges:
                neighbor_node = None
                relationship = edge.get('label', 'related to')
                if edge['source'] == node_id and edge['target'] not in neighbors:
                    neighbor_node = edge['target']
                    neighbor_details_list.append(f"{neighbor_node} ({relationship})")
                elif edge['target'] == node_id and edge['source'] not in neighbors:
                    neighbor_node = edge['source']
                    # Adjust relationship description if needed based on edge direction/type
                    rev_relationship = relationship # Keep label simple for now
                    neighbor_details_list.append(f"{neighbor_node} ({rev_relationship})")

                if neighbor_node:
                    neighbors.add(neighbor_node)

            # Build subgraph elements
            sub_nodes_data = [n for n in all_nodes if n['id'] in neighbors]
            sub_edges_data = [e for e in all_edges if e['source'] in neighbors and e['target'] in neighbors]

            # Convert to Cytoscape format
            new_elements = []
            for node in sub_nodes_data:
                 details = {k: v for k, v in node.items() if k not in ['id', 'label', 'color']}
                 node_data = {'id': node['id'], 'label': node['label'], 'type': node['type'], 'size': 25 if node['type'] == 'Event' else (15 if node['type'] == 'Individual' else 20), 'details': json.dumps(details) }
                 node_class = node['type']
                 if "Country" in node.get('category', ''): node_class = "Country"
                 elif any(sub in node.get('category', '') for sub in ["Organization", "Union", "Military Alliance", "International Body", "Legislative Body", "State Force", "Military", "Paramilitary", "Group", "Party", "Community", "Government"]): node_class = "Organization"
                 elif node['type'] == 'Individual': node_class = "Individual"
                 elif node['type'] == 'Event': node_class = "Event"
                 else: node_class = "Actor"
                 new_elements.append({'data': node_data, 'classes': node_class})

            for edge in sub_edges_data:
                 new_elements.append({'data': {'source': edge['source'], 'target': edge['target'], 'label': edge.get('label', ''), 'width': 2 if edge['type'] == 'causal' else 1, 'edge_type': edge['type'] }, 'classes': edge['type'] })

            # Create output message
            tap_output_msg_content = [html.H5(f"Focus on: {node_label}")]
            if neighbor_details_list:
                tap_output_msg_content.append(html.P(f"Connected to {len(neighbor_details_list)} node(s):"))
                tap_output_msg_content.append(html.Ul([html.Li(detail) for detail in sorted(neighbor_details_list)]))
            else:
                tap_output_msg_content.append(html.P("No direct connections found in the dataset."))
            tap_output_msg = dbc.Alert(tap_output_msg_content, color="info", style={'maxHeight': '300px', 'overflowY': 'auto'})

            return new_elements, tap_output_msg, debug_info

        # Default: If no specific action matched or search is empty, show full graph
        # (This part completes your snippet)
        debug_info += " Default action: showing full graph."
        elements = create_cytoscape_elements('full', search_text=search_value or "") # Apply search if present
        tap_output_msg = f"Showing search results for '{search_value}'." if search_value else "Click on a node to see its subgraph details."
        return elements, tap_output_msg, debug_info

    except Exception as e:
        error_message = f"Error in filter_subgraph callback: {e}"
        print(error_message)
        traceback.print_exc()
        # Return the full graph and an error message
        return create_cytoscape_elements('full'), dbc.Alert(error_message, color="danger"), debug_info


# --- [ Other Callbacks (update_timeline, update_actor_view) remain the same ] ---
# ... (paste previous versions of update_timeline and update_actor_view here) ...
@app.callback( [Output('timeline-graph', 'figure'), Output('event-details', 'children')], [Input('event-type-dropdown', 'value'), Input('date-range-picker', 'start_date'), Input('date-range-picker', 'end_date'), Input('timeline-graph', 'clickData')] )
def update_timeline(selected_types, start_date_str, end_date_str, click_data):
    # Uses revised create_timeline_figure with add_shape
    filtered_df = timeline_df.copy()
    if selected_types: filtered_df = filtered_df[filtered_df['type'].isin(selected_types)]
    if start_date_str and end_date_str:
        try: start_date = pd.to_datetime(start_date_str); end_date = pd.to_datetime(end_date_str); filtered_df = filtered_df[(filtered_df['date_parsed'] >= start_date) & (filtered_df['date_parsed'] <= end_date)]
        except ValueError: print(f"Error parsing dates: {start_date_str}, {end_date_str}")
    fig = create_timeline_figure(filtered_df)
    event_details_children = html.Div("Click on an event in the timeline above to see details.")
    ctx = dash.callback_context; triggered_id = ctx.triggered[0]['prop_id'].split('.')[0] if ctx.triggered else None
    if triggered_id == 'timeline-graph' and click_data:
        try:
            event_title = click_data['points'][0]['hovertext']
            event_data = timeline_df[timeline_df['title'] == event_title].iloc[0]
            preceded_by = causal_links_df[causal_links_df['target_event'] == event_title]['source_event'].tolist()
            led_to = causal_links_df[causal_links_df['source_event'] == event_title]['target_event'].tolist()
            event_details_children = dbc.Card([ dbc.CardHeader(html.H5(event_data['title'])), dbc.CardBody([ dbc.Row([ dbc.Col(html.P([html.Strong("Date: "), event_data['date']]), md=6), dbc.Col(html.P([html.Strong("Location: "), event_data['location']]), md=6), ]), html.P([html.Strong("Type: "), event_data['type']]), html.P([html.Strong("Actors Involved: "), event_data['actors_str']]), html.H6("Summary:", style={'marginTop': '10px'}), html.P(event_data['summary']), html.H6("Causal Relationships:", style={'marginTop': '10px'}), html.Div([html.Strong("Preceded by: "), html.Span(", ".join(preceded_by) if preceded_by else "None")]), html.Div([html.Strong("Led to: "), html.Span(", ".join(led_to) if led_to else "None")]) ]) ], color="light")
        except (KeyError, IndexError, TypeError) as e: print(f"Error processing timeline click data: {e}"); event_details_children = dbc.Alert("Error displaying event details.", color="danger")
    return fig, event_details_children

@app.callback( [Output('actor-network-container', 'style'), Output('actor-table-container', 'style'), Output('actor-details', 'children')], [Input('actor-view-toggle', 'value'), Input('actor-network-graph', 'clickData'), Input('actors-table', 'active_cell')], [State('actors-table', 'data')] )
def update_actor_view(view_option, network_click, table_cell, table_data):
    network_style = {'display': 'block'} if view_option == 'network' else {'display': 'none'}
    table_style = {'display': 'block'} if view_option == 'table' else {'display': 'none'}
    actor_details_children = html.Div("Select an actor from the network or table above to view details.")
    ctx = dash.callback_context; triggered_id = ctx.triggered[0]['prop_id'].split('.')[0] if ctx.triggered else None
    actor_name = None
    if triggered_id == 'actor-network-graph' and network_click:
        try: actor_name = network_click['points'][0]['text']
        except (KeyError, IndexError, TypeError): actor_name = None
    elif triggered_id == 'actors-table' and table_cell and table_data:
        try: actor_name = table_data[table_cell['row']]['Name']
        except (KeyError, IndexError, TypeError): actor_name = None
    if actor_name:
        actor_info = None
        actor_match = actors_df[actors_df['name'] == actor_name]
        if not actor_match.empty:
            actor_data = actor_match.iloc[0]; events = [e['target'] for e in actor_event_edges if e['source'] == actor_name]
            actor_info = {'name': actor_data['name'], 'type': actor_data['type'], 'role': actor_data['role'], 'events': sorted(list(set(events)))}
        else:
            ind_match = individuals_df[individuals_df['name'] == actor_name]
            if not ind_match.empty:
                ind_data = ind_match.iloc[0]; events = [e['target'] for e in individual_event_edges if e['source'] == actor_name]
                actor_info = {'name': ind_data['name'], 'type': f"Individual ({ind_data['role']})", 'role': ind_data['description'], 'involvement': ind_data['involvement'], 'events': sorted(list(set(events)))}
        if actor_info:
            actor_details_children = dbc.Card([ dbc.CardHeader(html.H5(actor_info['name'])), dbc.CardBody([ html.P([html.Strong("Type: "), actor_info['type']]), html.P([html.Strong("Role/Description: "), actor_info['role']]), html.H6("Detailed Involvement:", style={'marginTop': '10px'}) if 'involvement' in actor_info else None, html.P(actor_info['involvement']) if 'involvement' in actor_info else None, html.H6("Events Involved In:", style={'marginTop': '10px'}), html.Ul([html.Li(event) for event in actor_info['events']]) if actor_info['events'] else html.P("No specific events linked.") ]) ], color="light")
        else: actor_details_children = dbc.Alert(f"Details not found for '{actor_name}'.", color="warning")
    return network_style, table_style, actor_details_children


# ----------------------------------------------------------------------------------
# RUN THE APPLICATION
# ----------------------------------------------------------------------------------
# --- [ if __name__ == '__main__': block remains the same ] ---
if __name__ == '__main__':
    print("Attempting to start Dash server...")
    print(f"Current Working Directory: {os.getcwd()}")
    app.run(debug=True, host='0.0.0.0', port=8052)