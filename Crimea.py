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
import dash_cytoscape as cyto # Import Cytoscape
import os
import traceback
import uuid # For Cytoscape element generation if needed
import copy # For deep copying stylesheets

# Load Cytoscape extensions - important for layouts
try:
    cyto.load_extra_layouts()
except Exception as e:
    print(f"Warning: Could not load extra Cytoscape layouts: {e}")

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
            #if debug_mode: print(f"DEBUG (parse_date): Parsed simple range: '{original_date_str}' -> '{date_str}'")

        # Complex range match: "22 Apr - 3 May 2014" -> use the first day
        range_match_complex = re.match(r"(\d{1,2}\s+\w{3})\s*-\s*\d{1,2}\s+\w{3}\s+(\d{4})", date_str)
        if range_match_complex:
            day_month_start, year = range_match_complex.groups()
            date_str = f"{day_month_start} {year}"
            #if debug_mode: print(f"DEBUG (parse_date): Parsed complex range: '{original_date_str}' -> '{date_str}'")

        formats_to_try = ["%d %b %Y"]
        parsed_date = None
        for fmt in formats_to_try:
            try:
                parsed_date = datetime.strptime(date_str, fmt)
                return parsed_date # Success
            except ValueError:
                continue # Try next format

        # Fallback if formats failed
        print(f"Warning: Could not parse date string '{original_date_str}' (processed as '{date_str}') with known formats.")
        return datetime(2014, 2, 27) # Default fallback

    except Exception as e:
        print(f"Error during date parsing for: '{original_date_str}', Processed str: '{date_str}'. Error: {e}")
        return datetime(2014, 2, 27) # Default fallback

# ------------------------------------------------------------------------------
# FULL DATA LISTS (Standardized Hyphens)
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
        "date": "3-8 Mar 2014", "title": "Standoff - Ukraine Isolated; OSCE Observers Blocked", "type": "Diplomatic/Military", # Standardized hyphen
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
        "summary": "Crimea holds a hastily organized referendum on its status, under heavy military presence with checkpoints at polling stations. The choice is union with Russia or reverting to Crimea's 1992 constitution (no option to remain with Ukraine). The official result claims 95-97% in favor of joining Russia with an 83% turnout; however, most Western governments denounce the vote as illegitimate." # Standardized hyphen
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
        "summary": "The UN General Assembly votes 100-11 (with 58 abstentions) to affirm Ukraine's territorial integrity and declare the referendum void. The resolution calls on states not to recognize any change in Crimea's status, highlighting Russia's international isolation." # Standardized hyphen
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
    {"name": "Ukraine (post-revolution interim government)", "type": "Country (Victim State)", "role": "Opposed separatist moves at every step. Declared Russia's actions a military invasion and maintained that Crimea remained Ukrainian, passing laws designating it 'occupied.'", "events": ["Ukrainian President Ousted by Parliament", "Standoff - Ukraine Isolated; OSCE Observers Blocked", "Kyiv Declares Crimea 'Occupied Territory'"]},
    {"name": "United States", "type": "Country (International Responder)", "role": "Led Western condemnation and sanctions. Imposed travel bans and asset freezes on Russian officials and separatist leaders.", "events": ["UN Security Council Draft Resolution Vetoed by Russia", "Crimea Moves to Annexation; Western Sanctions Begin", "G7 Nations Suspend Russia from G8"]},
    {"name": "European Union (EU) and G7", "type": "Supranational Union / Economic bloc", "role": "Condemned Russia's actions and implemented coordinated sanctions. Declared the referendum illegal and suspended Russia from the G8.", "events": ["Crimea Moves to Annexation; Western Sanctions Begin", "G7 Nations Suspend Russia from G8"]},
    {"name": "United Nations", "type": "International Organization", "role": "Served as a global forum; passed Resolution 68/262 affirming Ukraine's territorial integrity and declaring the referendum void.", "events": ["UN Security Council Draft Resolution Vetoed by Russia", "UN General Assembly Deems Referendum Invalid"]},
    {"name": "NATO (North Atlantic Treaty Organization)", "type": "Military Alliance", "role": "Condemned Russia's intervention as a breach of international law and boosted defenses in Eastern Europe.", "events": ["Standoff - Ukraine Isolated; OSCE Observers Blocked"]},
    {"name": "OSCE (Organization for Security & Co-operation in Europe)", "type": "International Organization", "role": "Deployed observers to monitor events in Crimea, though they were blocked by Russian forces.", "events": ["Standoff - Ukraine Isolated; OSCE Observers Blocked"]},
    {"name": "Crimean Supreme Council (Parliament)", "type": "Regional Legislative Body", "role": "Seized by armed men and used as a rubber-stamp to vote for secession and join Russia.", "events": ["Armed Men Seize Crimean Parliament; New PM Installed", "Crimean Parliament Votes to Secede and Join Russia", "Crimea's 'Declaration of Independence'", "Crimean Referendum Held Under Occupation"]},
    {"name": "City of Sevastopol Administration", "type": "Local Government (City)", "role": "Formed a parallel administration; elected Aleksei Chaly as de facto mayor.", "events": ["Pro-Russian Rally in Crimea; Parallel Authority in Sevastopol", "Crimea's 'Declaration of Independence'"]},
    {"name": "Russian Armed Forces (Black Sea Fleet)", "type": "Military", "role": "Physically occupied Crimea by seizing key sites and blockading Ukrainian bases.", "events": ["Russian Troops and 'Self-Defense' Forces Take Control", "Standoff - Ukraine Isolated; OSCE Observers Blocked"]},
    {"name": "Crimean Tatars and Mejlis", "type": "Ethnic/Cultural Group", "role": "Strongly opposed the annexation. Organized protests and later faced repression.", "events": ["Clashes at Crimean Parliament between Rival Rallies", "Tatar Leader Barred; Standoff at Crimea Border", "Defying Ban, Tatars Commemorate Deportation Anniversary"]},
    {"name": "Crimean 'Self-Defense' Forces", "type": "Paramilitary Militia", "role": "Local militias that operated alongside Russian troops to secure the region.", "events": ["Russian Troops and 'Self-Defense' Forces Take Control", "Tatar Leader Barred; Standoff at Crimea Border"]},
    {"name": "Ukraine (Yanukovych gov't)", "type": "Country (Pre-Revolution Gov't)", "role": "The government before Euromaidan climax.", "events": ["Ukraine Drops EU Deal; Protests Begin (Euromaidan)"]},
    {"name": "EU", "type": "Supranational Union", "role": "Intended partner for the EU Association Agreement.", "events": ["Ukraine Drops EU Deal; Protests Begin (Euromaidan)", "Crimea Moves to Annexation; Western Sanctions Begin", "G7 Nations Suspend Russia from G8"]}, # Merged events
    {"name": "Protesters", "type": "Group (Civil)", "role": "Euromaidan demonstrators.", "events": ["Deadly Clashes in Kyiv ('Maidan Massacre')"]},
    {"name": "Ukraine security forces", "type": "State Force", "role": "Security forces under Yanukovych.", "events": ["Deadly Clashes in Kyiv ('Maidan Massacre')"]},
    {"name": "Ukraine (Parliament)", "type": "National Legislative Body", "role": "The legislature that ousted Yanukovych.", "events": ["Ukrainian President Ousted by Parliament", "Kyiv Declares Crimea 'Occupied Territory'"]}, # Merged events
    {"name": "Sevastopol locals", "type": "Group (Civil)", "role": "Pro-Russian residents of Sevastopol.", "events": ["Pro-Russian Rally in Crimea; Parallel Authority in Sevastopol"]},
    {"name": "Russian Unity party", "type": "Political Party", "role": "Minor pro-Russian party led by Aksyonov.", "events": ["Clashes at Crimean Parliament between Rival Rallies"]},
    {"name": "Unmarked Russian special forces", "type": "Military (Covert)", "role": "Initial troops seizing key sites ('Little Green Men').", "events": ["Armed Men Seize Crimean Parliament; New PM Installed"]},
    {"name": "Crimean self-defense militias", "type": "Paramilitary Militia", "role": "Militias supporting the takeover.", "events": ["Russian Troops and 'Self-Defense' Forces Take Control"]},
    {"name": "Russian Federation Council", "type": "National Legislative Body (Upper House)", "role": "Approved the use of force.", "events": ["Russia Authorizes Use of Force in Ukraine", "Annexation Legalized in Russian Law"]}, # Merged events
    {"name": "Ukraine interim government", "type": "National Government (Interim)", "role": "Formed after Yanukovych fled.", "events": ["Standoff - Ukraine Isolated; OSCE Observers Blocked"]},
    {"name": "Russian forces", "type": "Military", "role": "General term for Russian troops.", "events": ["Standoff - Ukraine Isolated; OSCE Observers Blocked"]},
    {"name": "Crimean gov't (Aksyonov)", "type": "Regional Government (De Facto)", "role": "The separatist government installed on 27 Feb.", "events": ["Crimean Parliament Votes to Secede and Join Russia"]},
    #{"name": "Aleksei Chaly", "type": "Regional Leader (De Facto)", "role": "Elected as de facto mayor of Sevastopol.", "events": ["Pro-Russian Rally in Crimea; Parallel Authority in Sevastopol", "Crimea's 'Declaration of Independence'"]}, # Covered by Individuals
    #{"name": "Barack Obama", "type": "Country (International Responder)", "role": "Imposed sanctions and led international opposition.", "events": ["UN Security Council Draft Resolution Vetoed by Russia", "Crimea Moves to Annexation; Western Sanctions Begin", "G7 Nations Suspend Russia from G8"]}, # Covered by Individuals
    {"name": "Crimean Parliament", "type": "Regional Legislative Body", "role": "Autonomous Republic of Crimea legislature.", "events": ["Clashes at Crimean Parliament between Rival Rallies", "Armed Men Seize Crimean Parliament; New PM Installed", "Crimea Moves to Annexation; Western Sanctions Begin"]},
    {"name": "Crimean Parliament & Sevastopol Council", "type": "Legislative Bodies (Joint)", "role": "Joint bodies issuing independence declaration.", "events": ["Crimea's 'Declaration of Independence'"]},
    {"name": "United Nations Security Council (P5: Russia, US, UK, France, China)", "type": "International Body", "role": "UN body where Russia vetoed resolution.", "events": ["UN Security Council Draft Resolution Vetoed by Russia"]},
    {"name": "Crimean de facto authorities", "type": "Regional Government (De Facto)", "role": "Authorities organizing the referendum.", "events": ["Crimean Referendum Held Under Occupation"]},
    {"name": "Crimean voters", "type": "Group (Civil)", "role": "Participants in the disputed referendum.", "events": ["Crimean Referendum Held Under Occupation"]},
    {"name": "USA", "type": "Country (International Responder)", "role": "Imposed sanctions.", "events": ["Crimea Moves to Annexation; Western Sanctions Begin"]},
    {"name": "Russian Parliament", "type": "National Legislative Body", "role": "Ratified annexation treaty.", "events": ["Treaty of Accession: Russia Annexes Crimea"]},
    {"name": "Russian State Duma & Federation Council", "type": "National Legislative Bodies", "role": "Both houses legalizing annexation.", "events": ["Annexation Legalized in Russian Law"]},
    {"name": "G7 (USA, UK, France, Germany, Italy, Canada, Japan) & EU", "type": "International Grouping", "role": "Suspended Russia from G8.", "events": ["G7 Nations Suspend Russia from G8"]},
    {"name": "UN General Assembly (193 member states)", "type": "International Body", "role": "Passed resolution deeming referendum invalid.", "events": ["UN General Assembly Deems Referendum Invalid"]},
    {"name": "Ukraine (Parliament & Gov't)", "type": "National Government & Legislature", "role": "Declared Crimea occupied.", "events": ["Kyiv Declares Crimea 'Occupied Territory'"]},
    {"name": "Crimean authorities", "type": "Regional Government (De Facto)", "role": "Authorities enforcing ban on Dzhemilev.", "events": ["Tatar Leader Barred; Standoff at Crimea Border"]},
    {"name": "Crimean Tatar community", "type": "Ethnic/Cultural Group", "role": "Community protesting leader's ban.", "events": ["Tatar Leader Barred; Standoff at Crimea Border"]},
    {"name": "Crimean Tatars (Mejlis)", "type": "Ethnic/Cultural Group", "role": "Community defying ban on commemoration.", "events": ["Defying Ban, Tatars Commemorate Deportation Anniversary"]},
    #{"name": "Sergey Aksyonov (Crimea PM)", "type": "Regional Leader (De Facto)", "role": "Issued ban on mass gatherings.", "events": ["Defying Ban, Tatars Commemorate Deportation Anniversary"]}, # Covered by Individuals
    #{"name": "Petro Poroshenko", "type": "Individual", "role": "President of Ukraine from 7 Jun 2014", "events": ["New Ukrainian President Elected, Vows to Reclaim Crimea"]}, # Covered by Individuals
    {"name": "Ukrainian voters", "type": "Group (Civil)", "role": "Elected Poroshenko.", "events": ["New Ukrainian President Elected, Vows to Reclaim Crimea"]},
    {"name": "Russian gov't", "type": "National Government", "role": "Government opposing Poroshenko's stance.", "events": ["New Ukrainian President Elected, Vows to Reclaim Crimea"]}
]
individuals = [
    {"name": "Vladimir Putin", "role": "President of Russia", "description": "Principal architect of the annexation", "involvement": "Putin directed the strategy to take Crimea: on 22-23 Feb he convened security chiefs and declared 'we must start working on returning Crimea to Russia.' He deployed special forces and later signed the accession treaty on 18 Mar, framing the move as correcting a historical injustice.", "events": ["Russia Authorizes Use of Force in Ukraine", "Treaty of Accession: Russia Annexes Crimea"]},
    {"name": "Sergey Aksyonov", "role": "Crimean Prime Minister", "description": "Pro-Russian politician installed as leader of Crimea", "involvement": "Elevated on 27 Feb during the coup at the parliament, he consolidated local power, called for the 16 Mar referendum, signed the accession treaty, and issued ban on mass gatherings.", "events": ["Armed Men Seize Crimean Parliament; New PM Installed", "Russia Authorizes Use of Force in Ukraine", "Crimean Parliament Votes to Secede and Join Russia", "Treaty of Accession: Russia Annexes Crimea", "Defying Ban, Tatars Commemorate Deportation Anniversary"]}, # Consolidated
    {"name": "Viktor Yanukovych", "role": "President of Ukraine until 22 Feb 2014", "description": "Ousted president whose downfall set the stage", "involvement": "His removal triggered events in both Kyiv and Crimea. He later resurfaced in Russia claiming legitimacy.", "events": ["Ukrainian President Ousted by Parliament"]},
    {"name": "Oleksandr Turchynov", "role": "Acting President of Ukraine", "description": "Interim head of state after Yanukovych's ouster", "involvement": "Faced the challenge of Crimea and mobilized Ukrainian forces and diplomacy, while avoiding armed escalation.", "events": ["Ukrainian President Ousted by Parliament", "Standoff - Ukraine Isolated; OSCE Observers Blocked"]},
    {"name": "Barack Obama", "role": "President of the United States", "description": "Led the international response", "involvement": "Warned Russia of costs for intervention and coordinated sanctions with the EU.", "events": ["UN Security Council Draft Resolution Vetoed by Russia", "Crimea Moves to Annexation; Western Sanctions Begin", "G7 Nations Suspend Russia from G8"]},
    {"name": "Mustafa Dzhemilev", "role": "Former Chairman of Crimean Tatar Mejlis", "description": "Iconic leader of the Crimean Tatars", "involvement": "Urged peaceful resistance and boycotted the referendum; later was barred from Crimea, sparking a tense border standoff.", "events": ["Tatar Leader Barred; Standoff at Crimea Border"]},
    {"name": "Refat Chubarov", "role": "Chairman of the Mejlis of Crimean Tatars", "description": "Leader of the Crimean Tatar community", "involvement": "Coordinated resistance, organized protests, and defied bans on commemorations.", "events": ["Clashes at Crimean Parliament between Rival Rallies", "Defying Ban, Tatars Commemorate Deportation Anniversary"]},
    {"name": "Aleksei Chaly", "role": "De facto Mayor of Sevastopol", "description": "Local pro-Russian businessman", "involvement": "Installed as mayor by pro-Russian crowds; organized self-defense units and coordinated with Russian forces.", "events": ["Pro-Russian Rally in Crimea; Parallel Authority in Sevastopol", "Crimea's 'Declaration of Independence'"]},
    {"name": "Arseniy Yatsenyuk", "role": "Acting Prime Minister of Ukraine", "description": "Head of the interim government", "involvement": "Vowed that Crimea remains Ukrainian and signed the occupied territory law.", "events": ["Kyiv Declares Crimea 'Occupied Territory'"]},
    {"name": "Petro Poroshenko", "role": "President of Ukraine from 7 Jun 2014", "description": "Elected president who vowed to reclaim Crimea", "involvement": "Won the May 2014 election and reinforced Ukraine's claim to Crimea.", "events": ["New Ukrainian President Elected, Vows to Reclaim Crimea"]}
]
causal_links = [
    {"source_event": "Ukraine Drops EU Deal; Protests Begin (Euromaidan)", "target_event": "Deadly Clashes in Kyiv ('Maidan Massacre')", "relationship": "Escalation", "description": "The suspension of EU agreement plans sparked initial protests that escalated into deadly violence."},
    {"source_event": "Deadly Clashes in Kyiv ('Maidan Massacre')", "target_event": "Ukrainian President Ousted by Parliament", "relationship": "Direct Causation", "description": "The loss of life and chaos led to Yanukovych's removal."},
    {"source_event": "Ukrainian President Ousted by Parliament", "target_event": "Pro-Russian Rally in Crimea; Parallel Authority in Sevastopol", "relationship": "Reaction", "description": "The ousting of Yanukovych triggered pro-Russian mobilization in Crimea."},
    {"source_event": "Pro-Russian Rally in Crimea; Parallel Authority in Sevastopol", "target_event": "Clashes at Crimean Parliament between Rival Rallies", "relationship": "Polarization", "description": "Initial demonstrations led to counter-protests and clashes at the parliament."},
    {"source_event": "Clashes at Crimean Parliament between Rival Rallies", "target_event": "Armed Men Seize Crimean Parliament; New PM Installed", "relationship": "Pretext", "description": "The unrest provided a pretext for Russian forces to seize the parliament."},
    {"source_event": "Armed Men Seize Crimean Parliament; New PM Installed", "target_event": "Russian Troops and 'Self-Defense' Forces Take Control", "relationship": "Expansion", "description": "After seizing the parliament, Russian forces expanded control over Crimea."},
    {"source_event": "Russian Troops and 'Self-Defense' Forces Take Control", "target_event": "Russia Authorizes Use of Force in Ukraine", "relationship": "Retroactive Legalization", "description": "Force was later legally authorized by the Russian parliament."},
    {"source_event": "Russia Authorizes Use of Force in Ukraine", "target_event": "Standoff - Ukraine Isolated; OSCE Observers Blocked", "relationship": "Military Enforcement", "description": "Authorization allowed Russian forces to block international observers."},
    {"source_event": "Standoff - Ukraine Isolated; OSCE Observers Blocked", "target_event": "Crimean Parliament Votes to Secede and Join Russia", "relationship": "Political Cover", "description": "The absence of external oversight enabled a vote for secession."},
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

# ------------------------------------------------------------------------------
# DataFrame conversions and derived lists/sets
# ------------------------------------------------------------------------------
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

node_types = { "Event": "#4285F4", "Actor": "#EA4335", "Country": "#FBBC05", "Organization": "#34A853", "Individual": "#8F44AD", "Location": "#F39C12", "Method": "#3498DB", "Outcome": "#E74C3C" }

# Prepare node/edge lists for Cytoscape (base data)
event_nodes = []
for _, r in events_df.iterrows():
    details = r.to_dict()
    details.pop('title', None) # Remove fields already used in primary data
    details.pop('date_parsed', None)
    event_nodes.append({'id': r['title'], 'label': r['title'], 'type': 'Event', 'color': node_types['Event'], 'details_dict': details})

actor_nodes = []
for _, r in actors_df.iterrows():
    type_str = r.get('type', '')
    color = node_types['Actor']
    node_class = 'Actor'
    if "Country" in type_str: color, node_class = node_types['Country'], 'Country'
    elif any(sub in type_str for sub in ["Organization", "Union", "Alliance", "Body", "Legislative", "Force", "Military", "Paramilitary", "Group", "Party", "Community", "Government", "Grouping", "Council", "Administration"]):
        color, node_class = node_types['Organization'], 'Organization'
    details = r.to_dict()
    details.pop('name', None)
    actor_nodes.append({'id': r['name'], 'label': r['name'], 'type': node_class, 'color': color, 'details_dict': details})

individual_nodes = []
for _, r in individuals_df.iterrows():
    details = r.to_dict()
    details.pop('name', None)
    individual_nodes.append({'id': r['name'], 'label': r['name'], 'type': 'Individual', 'color': node_types['Individual'], 'details_dict': details})

all_nodes_base = event_nodes + actor_nodes + individual_nodes
node_ids = {n['id'] for n in all_nodes_base}

causal_edges = [{'source': r['source_event'], 'target': r['target_event'], 'label': r['relationship'], 'type': 'causal', 'details_dict': r.to_dict()} for i, r in causal_links_df.iterrows() if r['source_event'] in node_ids and r['target_event'] in node_ids]

actor_event_edges = [{'source': a['id'], 'target': e, 'label': 'involved_in', 'type': 'participation', 'details_dict': {'relation': 'involved_in'}} for a in actor_nodes for e in a['details_dict'].get('events', []) if a['id'] in node_ids and e in node_ids]
individual_event_edges = [{'source': ind['id'], 'target': e, 'label': 'participated_in', 'type': 'participation', 'details_dict': {'relation': 'participated_in'}} for ind in individual_nodes for e in ind['details_dict'].get('events', []) if ind['id'] in node_ids and e in node_ids]

all_edges_base = causal_edges + actor_event_edges + individual_event_edges


# --- Data for Actor-Only Graph (Nodes: Actors/Individuals, Edges: Shared Events) ---
actor_individual_nodes_cy = [n for n in all_nodes_base if n['type'] in ['Country', 'Organization', 'Individual', 'Actor']]
actor_individual_ids = {n['id'] for n in actor_individual_nodes_cy}
actor_actor_edges_cy = []
event_participants = {}
for edge in actor_event_edges + individual_event_edges: event_participants.setdefault(edge['target'], set()).add(edge['source'])
shared_event_links = {}
for event, participants in event_participants.items():
    participants_list = sorted(list(p for p in participants if p in actor_individual_ids))
    for i in range(len(participants_list)):
        for j in range(i + 1, len(participants_list)): shared_event_links.setdefault(tuple(sorted((participants_list[i], participants_list[j]))), set()).add(event)
for (u, v), events_set in shared_event_links.items(): actor_actor_edges_cy.append({'source': u, 'target': v, 'label': f"{len(events_set)} shared", 'type': 'shared_event', 'details_dict': {'shared_events': list(events_set)}})

# ------------------------------------------------------------------------------
# DASH APPLICATION SETUP
# ------------------------------------------------------------------------------
app = dash.Dash(__name__, external_stylesheets=[dbc.themes.BOOTSTRAP], suppress_callback_exceptions=True)
server = app.server
app.config.suppress_callback_exceptions = True

# ------------------------------------------------------------------------------
# HELPER FUNCTIONS
# ------------------------------------------------------------------------------

# --- Legend ---
def create_consistent_legend():
    legend_items = [
        {"type": "Individual", "color": node_types["Individual"], "label": "Individual Actors", "shape": "diamond"},
        {"type": "Organization", "color": node_types["Organization"], "label": "Organizations/Groups", "shape": "rectangle"},
        {"type": "Country", "color": node_types["Country"], "label": "Countries", "shape": "rectangle"},
        {"type": "Actor", "color": node_types["Actor"], "label": "Other Actors", "shape": "rectangle"},
        {"type": "Event", "color": node_types["Event"], "label": "Events", "shape": "ellipse"},
    ]
    legend_row = dbc.Row([
        dbc.Col([
            html.H5("Legend:"),
            dbc.Row([
                *[dbc.Col([
                    html.Div([
                        html.Div(style={
                            'backgroundColor': item["color"], 'width': '20px', 'height': '20px',
                            'display': 'inline-block', 'marginRight': '5px', 'border': '1px solid #ccc',
                            'borderRadius': '50%' if item["shape"] == 'ellipse' else ('0' if item["shape"] == 'rectangle' else '3px'), # Use 3px for diamond approx
                            'transform': 'rotate(45deg)' if item["shape"] == 'diamond' else 'none',
                            'transformOrigin': 'center center' if item["shape"] == 'diamond' else 'none' # Ensure diamond rotates centrally
                        }),
                        html.Span(f" {item['label']}", style={'verticalAlign': 'middle'})
                    ], style={'marginBottom': '5px'})
                ], width=6, sm=4, md=2) for item in legend_items],
                dbc.Col([
                     html.Div([html.Span("─── ", style={'color': '#333', 'fontWeight':'bold'}), html.Span(" Causal Link", style={'verticalAlign': 'middle'})], style={'marginBottom': '5px'}),
                     html.Div([html.Span("- - - ", style={'color': '#999'}), html.Span(" Participation Link", style={'verticalAlign': 'middle'})], style={'marginBottom': '5px'}),
                     html.Div([html.Span("--- ", style={'color': '#6fa8dc', 'fontWeight':'bold'}), html.Span(" Shared Event Link", style={'verticalAlign': 'middle'})], style={'marginBottom': '5px'}),
                ], width=12, sm=4, md=2)
            ], justify="center")
        ], width=12)
    ], style={'marginTop': '20px', 'padding': '15px', 'border': '1px solid #ddd', 'backgroundColor': 'rgba(250, 250, 250, 0.9)'})
    return legend_row


# --- Base Cytoscape Stylesheet ---
# Note: font-size will be overridden by callbacks
default_stylesheet = [
    {'selector': 'node', 'style': { 'label': 'data(label)', 'font-size': '10px', 'width': 'mapData(size, 10, 40, 10, 40)', 'height': 'mapData(size, 10, 40, 10, 40)', 'text-valign': 'bottom', 'text-halign': 'center', 'text-margin-y': '6px', 'border-width': 1, 'border-color': '#555', 'text-wrap': 'wrap', 'text-max-width': '80px', 'background-opacity': 0.9, 'color': '#333' }},
    {'selector': '.Event', 'style': {'background-color': node_types['Event'], 'shape': 'ellipse'}},
    {'selector': '.Country', 'style': {'background-color': node_types['Country'], 'shape': 'rectangle'}},
    {'selector': '.Organization', 'style': {'background-color': node_types['Organization'], 'shape': 'rectangle'}},
    {'selector': '.Individual', 'style': {'background-color': node_types['Individual'], 'shape': 'diamond'}},
    {'selector': '.Actor', 'style': {'background-color': node_types['Actor'], 'shape': 'rectangle'}},
    {'selector': 'edge', 'style': { 'label': 'data(label)', 'font-size': '8px', 'curve-style': 'bezier', 'width': 'mapData(width, 1, 5, 1, 5)', 'text-opacity': 0.8, 'color': '#555' }}, # Adjusted edge width mapping
    {'selector': '.causal', 'style': { 'line-color': '#333', 'target-arrow-shape': 'vee', 'target-arrow-color': '#333', 'width': 2.5 }},
    {'selector': '.participation', 'style': { 'line-color': '#999', 'line-style': 'dashed', 'target-arrow-shape': 'vee', 'target-arrow-color': '#999', 'width': 1.5 }},
    {'selector': '.shared_event', 'style': { 'line-color': '#6fa8dc', 'line-style': 'solid', 'width': 'mapData(width, 1, 5, 1, 5)', 'opacity': 0.6 }}, # Adjusted width mapping
    {'selector': 'node:selected', 'style': { 'border-width': 4, 'border-color': 'black', 'border-opacity': 1, 'opacity': 1, 'z-index': 9999, 'font-weight': 'bold' }},
    {'selector': 'edge:selected', 'style': { 'width': 4, 'line-color': 'black', 'opacity': 1, 'z-index': 9998 }},
    {'selector': 'node:hover', 'style': { 'border-width': 3, 'border-color': '#333', 'border-opacity': 1, 'opacity': 1, 'font-weight': 'bold', 'shadow-blur': 5, 'shadow-color': '#333', 'shadow-opacity': 0.5 }},
    {'selector': 'edge:hover', 'style': { 'width': 3, 'line-color': '#333', 'opacity': 1 }}
]

# --- Helper function to update stylesheet font size ---
def update_stylesheet_font_size(base_stylesheet, font_size):
    """Creates a deep copy of the stylesheet and updates the node font size."""
    updated_stylesheet = copy.deepcopy(base_stylesheet)
    try:
        for style in updated_stylesheet:
            if style.get('selector') == 'node':
                style['style']['font-size'] = f'{font_size}px'
                break # Found the node style
    except Exception as e:
        print(f"Error updating stylesheet font size: {e}")
    return updated_stylesheet


# --- Cytoscape Element Generation ---
def create_cytoscape_elements(nodes_list=None, edges_list=None, graph_type='faro'):
    """
    Generates Cytoscape elements list from provided nodes and edges.
    graph_type distinguishes between 'faro' (all types) and 'actor' (actor/individual + shared event links).
    """
    nodes_to_use = nodes_list if nodes_list is not None else (actor_individual_nodes_cy if graph_type == 'actor' else all_nodes_base)
    edges_to_use = edges_list if edges_list is not None else (actor_actor_edges_cy if graph_type == 'actor' else all_edges_base)

    elements = []
    node_ids_in_set = {n['id'] for n in nodes_to_use}

    # Add nodes
    for node in nodes_to_use:
        details = node.get('details_dict', {}) # Use pre-processed details dict
        node_data_cy = {
            'id': node['id'],
            'label': node['label'],
            'type': node['type'],
            'size': 30 if node['type'] == 'Event' else (25 if node['type'] in ['Country', 'Organization'] else (15 if node['type'] == 'Individual' else 20)),
            'details_json': json.dumps(details, default=str) # Store details as JSON string for callbacks
        }
        elements.append({'data': node_data_cy, 'classes': node['type']}) # Use node type as class

    # Add edges
    for edge in edges_to_use:
        if edge['source'] in node_ids_in_set and edge['target'] in node_ids_in_set:
            details = edge.get('details_dict', {})
            edge_data = {
                'source': edge['source'],
                'target': edge['target'],
                'label': edge.get('label', ''),
                'edge_type': edge['type'],
                'details_json': json.dumps(details, default=str)
            }
            # Assign width based on type
            if edge['type'] == 'shared_event': edge_data['width'] = min(1 + len(details.get('shared_events', [])), 5)
            elif edge['type'] == 'causal': edge_data['width'] = 2.5
            else: edge_data['width'] = 1.5 # participation

            elements.append({'data': edge_data, 'classes': edge['type']})

    return elements


# --- Timeline Figure Creation ---
def create_timeline_figure(filtered_df=timeline_df):
    if filtered_df.empty:
        fig = go.Figure()
        fig.update_layout(title="No events match filters.", height=600, xaxis={'visible': False}, yaxis={'visible': False})
        return fig
    try:
        df_copy = filtered_df.copy()
        df_copy['date_parsed'] = pd.to_datetime(df_copy['date_parsed'])
        df_copy['end_date'] = df_copy['date_parsed'] + pd.Timedelta(hours=12)
        fig = px.timeline(
            df_copy, x_start='date_parsed', x_end='end_date', y='type', color='type',
            hover_name='title',
            hover_data={'date': True, 'location': True, 'actors_str': True, 'date_parsed': False, 'end_date': False, 'type': False},
            labels={"date_parsed": "Date", "type": "Event Type"}, title="Chronology of Crimea Annexation Events",
            color_discrete_map={ "Political": "#4285F4", "Civil Unrest": "#DB4437", "Civil/Political": "#F4B400", "Military/Political": "#0F9D58", "Military": "#AB47BC", "Diplomatic/Military": "#FF7043", "Political/Legal": "#42A5F5", "Diplomatic": "#FFEE58", "Political & Intl. Response": "#9CCC65", "Diplomatic/Legal": "#FFCA28", "Legal": "#BDBDBD", "Legal/Political": "#BDBDBD", "Political/Human Rights": "#EC407A", "Civil/Human Rights": "#7E57C2" }
        )
        key_dates = [{"date": "2014-02-27", "label": "Parliament Seized"}, {"date": "2014-03-16", "label": "Referendum"}, {"date": "2014-03-18", "label": "Annexation"}, {"date": "2014-03-27", "label": "UN Vote"}]
        shapes, annotations = [], []
        min_vis_date = timeline_df['date_parsed'].min() - pd.Timedelta(days=5)
        max_vis_date = timeline_df['date_parsed'].max() + pd.Timedelta(days=5)
        for kd in key_dates:
             try:
                 ts = pd.Timestamp(kd["date"])
                 if min_vis_date <= ts <= max_vis_date:
                     shapes.append(dict(type="line", xref="x", yref="paper", x0=ts, y0=0, x1=ts, y1=1, line=dict(color="grey", width=1, dash="dash")))
                     annotations.append(dict(x=ts, y=1.05, yref="paper", showarrow=False, text=kd["label"], font=dict(size=10), align="center"))
             except Exception as e: print(f"Error processing key date {kd['date']} for timeline markers: {e}")
        fig.update_layout(
            shapes=shapes, annotations=annotations, xaxis_type='date',
            xaxis=dict(tickformat="%d %b\n%Y", title_text="Date", range=[min_vis_date, max_vis_date]),
            yaxis=dict(title_text="Event Type"), height=600, margin=dict(l=20, r=20, t=50, b=20), title_x=0.5, title_font_size=20,
            hoverlabel=dict(bgcolor="white", font_size=12, namelength=-1), legend_title_text='Event Types'
        )
        return fig
    except Exception as e: print(f"ERROR in create_timeline_figure: {e}"); traceback.print_exc(); fig = go.Figure(); fig.add_annotation(text=f"Error creating timeline: {e}", showarrow=False); return fig.update_layout(height=600)


# --- Actors Table Creation ---
def create_actors_table():
    try:
        table_data = []
        # Combine actor and individual data for the table
        for _, actor in actors_df.iterrows():
            table_data.append({
                'Name': actor['name'],
                'Type': actor['type'], # Use the detailed type from data
                'Role/Description': actor['role']
            })
        for _, individual in individuals_df.iterrows():
            table_data.append({
                'Name': individual['name'],
                'Type': f"Individual ({individual['role']})", # Clarify it's an individual
                'Role/Description': individual['description']
            })
        return pd.DataFrame(table_data)
    except Exception as e:
        if debug_mode: print(f"Error creating actors table: {e}")
        traceback.print_exc()
        return pd.DataFrame(columns=['Name', 'Type', 'Role/Description'])

# ------------------------------------------------------------------------------
# DASH APP LAYOUT (Modifications for Font Sliders and Actor Search)
# ------------------------------------------------------------------------------
app.layout = dbc.Container([
    # Header Row
    dbc.Row([
        dbc.Col(html.A(html.Img(src='assets/rubase logo 4.svg', style={'height': '87px', 'marginTop': '15px'}), href="https://hcss.nl/rubase/", target="_blank"), width=2, className="d-flex justify-content-center align-items-center"),
        dbc.Col([html.H1("Crimea Annexation (2014): Interactive Analysis", style={'textAlign': 'center', 'marginTop': '20px', 'marginBottom': '20px'}), html.P("A comprehensive visualization based on the FARO ontology.", style={'textAlign': 'center', 'fontSize': '18px', 'marginBottom': '30px'})], width=8),
        dbc.Col(html.A(html.Img(src='assets/HCSS_Beeldmerk_Blauw_RGB.svg', style={'height': '87px', 'marginTop': '15px'}), href="https://hcss.nl", target="_blank"), width=2, className="d-flex justify-content-center align-items-center")
    ]),

    dbc.Tabs(id='tabs', active_tab="tab-1", children=[

        # ================= TAB 1: FARO Knowledge Graph =================
        dbc.Tab(label="FARO Knowledge Graph", tab_id="tab-1", children=[
            dbc.Row([
                dbc.Col(html.H3("FARO Ontology Network", style={'textAlign': 'center', 'marginTop': '20px'}), width=12),
                dbc.Col(html.P("Explore events, actors, and their links. Hover for info, click nodes for subgraphs.", style={'textAlign': 'center', 'marginBottom': '20px'}), width=12)
            ]),
            dbc.Row([
                dbc.Col([html.Label("Layout:"), dcc.Dropdown(id='cytoscape-layout-dropdown', options=[{'label': l.capitalize(), 'value': l} for l in ['cose', 'grid', 'circle', 'breadthfirst', 'dagre']], value='cose', clearable=False)], width=6, md=2),
                dbc.Col([html.Label("Search Nodes:"), dcc.Input(id="cytoscape-search-input", type="text", placeholder="Filter nodes...", debounce=True, style={"width": "100%"})], width=6, md=3),
                dbc.Col([html.Label("Node Font Size:"), dcc.Slider(id='faro-font-size-slider', min=6, max=18, step=1, value=10, marks={i: str(i) for i in range(6, 19, 2)}, tooltip={"placement": "bottom", "always_visible": False})], width=9, md=4), # Adjusted width
                dbc.Col([html.Button("Reset View", id="reset-btn", n_clicks=0, className="btn btn-secondary", style={"marginTop": "28px", "width":"100%"})], width=3, md=2)
            ], justify="start", align='bottom', style={'marginBottom': '20px'}), # Align start
            dbc.Row([ dbc.Col(dcc.Loading(id="loading-cytoscape", type="circle", children=[ cyto.Cytoscape(id='cytoscape-faro-network', elements=create_cytoscape_elements(graph_type='faro'), layout={'name': 'cose', 'idealEdgeLength': 100, 'nodeRepulsion': 40000, 'animate': False, 'fit': True, 'padding': 50}, style={'width': '100%', 'height': '700px', 'border': '1px solid #ddd'}, stylesheet=default_stylesheet, minZoom=0.1, maxZoom=2.5) ]), width=12) ]),
            dbc.Row([ dbc.Col([html.Div(id='cytoscape-hover-output', style={'marginTop': '10px', 'padding': '10px', 'border': '1px solid #ccc', 'borderRadius': '5px', 'fontSize': '14px', 'minHeight': '60px', 'backgroundColor': '#f9f9f9'}, children="Hover over a node or edge."), html.Div(id='cytoscape-tapNodeData-output', style={'marginTop': '15px', 'padding': '15px', 'border': '1px dashed #ccc', 'minHeight': '80px', 'backgroundColor': '#f0f0f0'}, children="Click a node for details and subgraph view.")], width=12) ]),
            create_consistent_legend()
        ]),

        # ================= TAB 2: Chronological Event Timeline =================
        dbc.Tab(label="Chronological Event Timeline", tab_id="tab-2", children=[
             dbc.Row([ dbc.Col(html.H3("Timeline of Key Events", style={'textAlign': 'center', 'marginTop': '20px'}), width=12), dbc.Col(html.P("Use filters to explore the sequence. Click event bubbles for details.", style={'textAlign': 'center', 'marginBottom': '20px'}), width=12) ]),
             dbc.Row([ dbc.Col([html.Label("Filter by Event Type:"), dcc.Dropdown(id='event-type-dropdown', options=[{'label': t, 'value': t} for t in sorted(timeline_df['type'].unique())], value=[], multi=True, placeholder="Select types...")], width=12, md=6), dbc.Col([html.Label("Date Range:"), dcc.DatePickerRange(id='date-range-picker', min_date_allowed=timeline_df['date_parsed'].min().date(), max_date_allowed=timeline_df['date_parsed'].max().date(), start_date=timeline_df['date_parsed'].min().date(), end_date=timeline_df['date_parsed'].max().date(), display_format='DD MMM YY', style={'width': '100%'})], width=12, md=6) ], justify="center", style={'marginBottom': '20px'}),
             dbc.Row([ dbc.Col(dcc.Loading(id='loading-timeline', type='circle', children=[dcc.Graph(id='timeline-graph', figure=create_timeline_figure(), style={'height': '600px'})]), width=12) ]),
             dbc.Row([ dbc.Col([html.H4("Event Details", style={'marginTop': '30px'}), dcc.Loading(id='loading-event-details', type='circle', children=[ html.Div(id='event-details', children=[dbc.Alert("Click an event bubble in the timeline.", color="info")], style={'marginTop': '10px', 'padding': '15px', 'border': '1px solid #eee', 'minHeight': '100px', 'backgroundColor': '#fdfdfd'}) ])], width=12) ]),
             dcc.Store(id='timeline-table')
        ]),

        # ================= TAB 3: Actors and Roles =================
        dbc.Tab(label="Actors and Roles", tab_id="tab-3", children=[
             dbc.Row([
                dbc.Col([
                    html.H3("Actor / Individual Relationships", style={'textAlign': 'center', 'marginTop': '20px'}),
                    html.P("Explore relationships (via shared events) or view a detailed table.", style={'textAlign': 'center', 'marginBottom': '20px'}),
                    dbc.RadioItems(id='actor-view-toggle', options=[{'label': 'Relationship Network', 'value': 'network'}, {'label': 'Detailed Table', 'value': 'table'}], value='network', inline=True, style={'textAlign': 'center', 'marginBottom': '20px'})
                ], width=12)
            ]),
            # Network View Container
            html.Div(id='actor-network-container', children=[
                dbc.Row([
                    dbc.Col([html.Label("Layout:"), dcc.Dropdown(id='cytoscape-actor-layout-dropdown', options=[{'label': l.capitalize(), 'value': l} for l in ['cose', 'grid', 'circle', 'concentric']], value='cose', clearable=False)], width=6, md=2),
                    dbc.Col([html.Label("Search Actors:"), dcc.Input(id="actor-search-input", type="text", placeholder="Filter actors...", debounce=True, style={"width": "100%"})], width=6, md=3), # Search Input
                    dbc.Col([html.Label("Node Font Size:"), dcc.Slider(id='actor-font-size-slider', min=6, max=18, step=1, value=10, marks={i: str(i) for i in range(6, 19, 2)}, tooltip={"placement": "bottom", "always_visible": False})], width=9, md=4), # Font Slider
                    dbc.Col([html.Button("Reset View", id="reset-actor-btn", n_clicks=0, className="btn btn-secondary", style={"marginTop": "28px", "width":"100%"})], width=3, md=2) # Shortened button text
                ], justify="start", align='bottom', style={'marginBottom': '10px'}),
                dbc.Row([ dbc.Col(dcc.Loading(id='loading-actor-network', type='circle', children=[ cyto.Cytoscape(id='cytoscape-actor-network', elements=create_cytoscape_elements(graph_type='actor'), layout={'name': 'cose', 'animate': False}, style={'width': '100%', 'height': '600px', 'border': '1px solid #ddd'}, stylesheet=default_stylesheet, minZoom=0.1, maxZoom=2.5) ]), width=12) ]),
                dbc.Row([ dbc.Col(html.Div(id='cytoscape-actor-hover-output', style={'marginTop': '10px', 'padding': '10px', 'border': '1px solid #ccc', 'borderRadius': '5px', 'fontSize': '14px', 'minHeight': '60px', 'backgroundColor': '#f9f9f9'}, children="Hover over an actor/individual or link."), width=12) ])
            ], style={'display': 'block'}),
            # Table View Container
            html.Div(id='actor-table-container', children=[
                 dcc.Loading(id="loading-actors-table", type="circle", children=[
                    dash_table.DataTable(
                        id='actors-table', columns=[{'name': i, 'id': i} for i in ['Name', 'Type', 'Role/Description']], data=create_actors_table().to_dict('records'),
                        style_table={'overflowX': 'auto'}, style_header={'backgroundColor': 'rgb(230, 230, 230)', 'fontWeight': 'bold', 'border': '1px solid lightgrey'}, style_cell={'textAlign': 'left', 'padding': '10px', 'whiteSpace': 'normal', 'height': 'auto', 'minWidth': '150px', 'width': 'auto', 'maxWidth': '400px', 'border': '1px solid lightgrey'},
                        page_size=15, filter_action="native", sort_action="native", sort_mode="multi", row_selectable="single", selected_rows=[], style_data_conditional=[{'if': {'row_index': 'odd'}, 'backgroundColor': 'rgb(248, 248, 248)'}]
                    )
                ])
            ], style={'display': 'none'}),
            # Actor Details Output Area (Common)
            dbc.Row([ dbc.Col([ html.H4("Actor/Individual Details", style={'marginTop': '30px'}), dcc.Loading(id='loading-actor-details', type='circle', children=[ html.Div(id='actor-details', children=[dbc.Alert("Click an actor node or select a table row.", color="info")], style={'marginTop': '10px', 'padding': '15px', 'border': '1px solid #eee', 'minHeight': '100px', 'backgroundColor': '#fdfdfd'}) ])], width=12) ]),
            create_consistent_legend()
        ]),

        # ================= TAB 4: Analysis & Perspectives =================
        dbc.Tab(label="Analysis & Perspectives", tab_id="tab-4", children=[
            dbc.Tabs(id='analysis-subtabs', active_tab="analysis-causal", children=[
                # --- Causal Patterns Sub-Tab ---
                dbc.Tab(label="Causal Patterns", tab_id="analysis-causal", children=[
                    dbc.Row(dbc.Col([ html.H4("Causal Chain Analysis", style={'marginTop': '20px'}), html.P("Explore the sequence of events leading to the annexation."), html.Ol([ html.Li("Ukrainian Revolution triggers protests."), html.Li("Pro-Russian sentiment rises in Crimea."), html.Li("Covert Russian special forces seize key sites."), html.Li("Pro-Russian leadership is installed."), html.Li("A hastily organized referendum is held."), html.Li("Formal annexation follows."), html.Li("International condemnation and sanctions are imposed."), html.Li("Control is consolidated in Crimea.") ], style={'marginBottom': '20px'}), ], width=12)),
                    dbc.Tabs(id="causal-subtabs-inner", active_tab="subtab-network", children=[
                        # --- Inner Tab: Causal Network Graph ---
                        dbc.Tab(label="Causal Chain Network", tab_id="subtab-network", children=[
                            dbc.Row([
                                dbc.Col([ # Controls Column
                                    html.Label("Layout:", style={'marginTop': '20px'}), dcc.Dropdown(id='cytoscape-causal-layout-dropdown', options=[{'label': l.capitalize(), 'value': l} for l in ['dagre', 'cose', 'breadthfirst', 'grid', 'circle']], value='dagre', clearable=False),
                                    html.Button("Reset Layout", id="reset-causal-layout", n_clicks=0, className="btn btn-sm btn-outline-secondary", style={"marginTop": "10px", "width":"100%"}),
                                    html.Label("Node Font Size:", style={'marginTop': '15px'}), dcc.Slider(id='causal-font-size-slider', min=6, max=20, step=1, value=10, marks={i: str(i) for i in range(6, 21, 2)}, tooltip={"placement": "bottom", "always_visible": False}),
                                ], width=12, md=3, style={'paddingTop': '20px'}),
                                dbc.Col([ # Graph Column
                                    dcc.Loading(id="loading-cytoscape-causal", type="default", children=[ cyto.Cytoscape(id='cytoscape-causal-graph', elements=create_cytoscape_elements(nodes_list=event_nodes, edges_list=causal_edges), layout={'name': 'dagre', 'rankDir': 'TB', 'animate': False, 'fit': True, 'padding': 50}, style={'width': '100%', 'height': '600px', 'border': '1px solid #ddd'}, stylesheet=default_stylesheet ) ])
                                ], width=12, md=9)
                            ])
                        ]),
                        # --- Inner Tab: Timeline Scatter Plot ---
                        dbc.Tab(label="Key Events Timeline", tab_id="subtab-timeline", children=[
                             dbc.Row([dbc.Col([html.H5("Critical Events in the Annexation Sequence", style={'marginTop': '20px', 'textAlign':'center'}), dcc.Graph(id='causal-flow-chart', figure=px.scatter(events_df.iloc[[0, 1, 2, 5, 6, 8, 9, 10, 12, 13, 14, 15, 17, 18, 19]], x='date_parsed', y='type', text='title', size=[20]*15, color='type', height=500, labels={"date_parsed": "Timeline", "type": "Event Category"}, title=None ).update_traces(mode='markers+text', textposition='top center', textfont_size=10 ).update_layout(yaxis={'visible': True, 'title': 'Event Category'}, xaxis_title="Timeline", showlegend=True, legend_title_text='Category', margin=dict(l=20, r=20, t=10, b=100)))], width=12)])
                        ]),
                    ]),
                ]),

                # --- International Response Sub-Tab ---
                dbc.Tab(label="International Response", tab_id="analysis-intl", children=[
                     dbc.Row([dbc.Col([html.H4("International Response Analysis", style={'marginTop': '20px'}), html.P("The international community responded with sanctions, diplomatic measures, and organizational actions."), dbc.Row([dbc.Col([html.H5("UN General Assembly Vote (Res 68/262)"), dcc.Graph(id='un-vote-chart', figure=px.pie(names=['In favor (Affirming Ukraine Integrity)', 'Against (Opposing Resolution)', 'Abstentions', 'Non-Voting'], values=[100, 11, 58, 24], title="UNGA Vote on Ukraine's Territorial Integrity (Mar 2014)", color_discrete_sequence=['#4285F4', '#EA4335', '#FBBC05', '#CCCCCC'], hole=0.3).update_traces(textinfo='percent+label'))], width=12, lg=6), dbc.Col([html.H5("Initial Sanctions Timeline (Mar-Jul 2014)"), dcc.Graph(id='sanctions-timeline', figure=px.timeline( pd.DataFrame([ dict(Sanction="US Initial Individual Sanctions", Start='2014-03-17', Finish='2014-03-20', Actor='US'), dict(Sanction="EU Initial Individual Sanctions", Start='2014-03-17', Finish='2014-03-21', Actor='EU'), dict(Sanction="G7 Suspends Russia from G8", Start='2014-03-24', Finish='2014-03-25', Actor='G7'), dict(Sanction="Expanded Sectoral Sanctions", Start='2014-07-16', Finish='2014-07-31', Actor='US/EU') ]), x_start="Start", x_end="Finish", y="Sanction", color="Actor", title="Timeline of Early Western Sanctions", labels={"Sanction": "Sanction Type/Action"} ).update_yaxes( categoryorder='array', categoryarray=[ "Expanded Sectoral Sanctions", "G7 Suspends Russia from G8", "EU Initial Individual Sanctions", "US Initial Individual Sanctions" ] ))], width=12, lg=6) ]), html.H5("Key Response Patterns:", style={'marginTop': '30px'}), html.Ul([ html.Li("Diplomatic condemnation and legal resolutions (UN)."), html.Li("Targeted economic sanctions (individual and sectoral) by US, EU, G7."), html.Li("Suspension from international forums (G8 -> G7)."), html.Li("Actions by international organizations (OSCE observer attempts)."), html.Li("Avoidance of direct military confrontation by Western powers."), html.Li("Long-term policy of non-recognition of the annexation.") ])], width=12) ])
                ]),

                # --- Legal & Territorial Impact Sub-Tab ---
                dbc.Tab(label="Legal & Territorial Impact", tab_id="analysis-legal", children=[
                     dbc.Row([dbc.Col([html.H4("Legal and Territorial Consequences", style={'marginTop': '20px'}), html.P("The annexation violated several international legal principles while altering Crimea's de facto status, leading to widespread non-recognition."), dbc.Row([dbc.Col([html.H5("Violations of International Law Cited"), html.Ul([ html.Li([html.Strong("UN Charter:"), " Principles of sovereignty, territorial integrity, and prohibition against the use of force to acquire territory."]), html.Li([html.Strong("Helsinki Final Act (1975):"), " Inviolability of frontiers and territorial integrity of States."]), html.Li([html.Strong("Budapest Memorandum (1994):"), " Security assurances to Ukraine respecting independence, sovereignty, and existing borders in exchange for denuclearization."]), html.Li([html.Strong("Russia-Ukraine Friendship Treaty (1997):"), " Recognition of existing borders and territorial integrity."]), html.Li([html.Strong("Ukrainian Constitution:"), " Territorial changes require a national referendum, not just regional."]) ]), html.H5("Russian Justifications / Counterarguments:", style={'marginTop': '15px'}), html.Ul([ html.Li("Protection of Russian-speaking population / ethnic Russians."), html.Li("Exercise of the right to self-determination by the people of Crimea (via referendum)."), html.Li("Alleged request for intervention/assistance (from Aksyonov/Yanukovych)."), html.Li("Correction of historical 'injustice' (1954 transfer to Ukrainian SSR)."), html.Li("Reference to Kosovo precedent (though widely disputed).") ])], width=12, lg=6), dbc.Col([html.H5("Territorial Impact - Crimea Profile"), dbc.Card(dbc.CardBody([ html.P([html.Strong("Status:"), " De facto administered by Russia; De jure recognized as Ukraine by most of the international community."]), html.P([html.Strong("Area: "), "~27,000 km²"]), html.P([html.Strong("Population (2014 est.): "), "~2.3 million"]), html.P([html.Strong("Strategic Importance: "), " Base for Russia's Black Sea Fleet (Sevastopol), control over Black Sea access."]), html.P([html.Strong("Economic Impact: "), " Integration into Russian economy, disruption of ties with mainland Ukraine, impact of sanctions, dependence on Russian infrastructure (e.g., Kerch Bridge)."]) ]), className="mb-3", outline=True, color="secondary"), html.P([html.Strong(f"Ongoing Situation (as of {datetime.now().strftime('%B %Y')}):"), " Crimea remains under Russian control and integrated into its legal/administrative system. Ukraine maintains its claim and non-recognition policies. The peninsula is a focal point in the ongoing Russo-Ukrainian War."], style={'marginTop': '20px', 'fontWeight': 'bold'})], width=12, lg=6) ]),], width=12)])
                ]),

            ]) # End Outer Analysis Tabs
        ]), # End Tab 4

    ]), # End Main Tabs

    # Footer
    dbc.Row([ dbc.Col([ html.Hr(style={'marginTop': '40px'}), html.P(["Data compiled from open sources.", html.Br(), f"Visualization generated on {datetime.now().strftime('%Y-%m-%d')}. Based on FARO ontology principles."], style={'textAlign': 'center', 'marginTop': '20px', 'color': '#666', 'fontSize': '14px'}) ], width=12) ])
], fluid=True, style={'fontFamily': 'Arial, sans-serif', 'backgroundColor': '#f8f9fa'})


# ------------------------------------------------------------------------------
# CALLBACKS
# ------------------------------------------------------------------------------

# --- Callback for Main Cytoscape Graph (Tab 1) ---
@app.callback(
    [Output('cytoscape-faro-network', 'elements'),
     Output('cytoscape-tapNodeData-output', 'children'),
     Output('cytoscape-faro-network', 'layout'),
     Output('cytoscape-search-input', 'value'),
     Output('cytoscape-faro-network', 'stylesheet')],
    [Input('cytoscape-faro-network', 'tapNodeData'),
     Input('reset-btn', 'n_clicks'),
     Input('cytoscape-search-input', 'value'),
     Input('cytoscape-layout-dropdown', 'value'),
     Input('faro-font-size-slider', 'value')],
)
def handle_main_cytoscape_interaction(tap_node, reset_clicks, search_value, layout_name, font_size):
    ctx = dash.callback_context
    triggered_prop_id = ctx.triggered[0]['prop_id'] if ctx.triggered else 'initial_load'
    trigger_id = triggered_prop_id.split('.')[0]

    # Default layout config (Cose is default)
    layout_config = {'name': layout_name or 'cose', 'animate': False, 'fit': True, 'padding': 50}
    if layout_name == 'dagre': layout_config['rankDir'] = 'TB'; layout_config['spacingFactor'] = 1.2
    elif layout_name == 'breadthfirst': layout_config['roots'] = '#Ukraine Drops EU Deal; Protests Begin (Euromaidan)'; layout_config['spacingFactor'] = 1.2
    elif layout_name == 'cose': layout_config.update({'idealEdgeLength': 100, 'nodeRepulsion': 50000, 'nodeOverlap': 10, 'gravity': 40}) # Tweaked Cose

    # Update stylesheet for font size
    stylesheet = update_stylesheet_font_size(default_stylesheet, font_size or 10)
    clear_search = dash.no_update

    # Handle Trigger Priority: Reset > Click > Search/Layout/Font Change
    if trigger_id == 'reset-btn':
        if debug_mode: print("FARO Reset triggered.")
        elements = create_cytoscape_elements(graph_type='faro')
        tap_output_msg = "Graph view reset. Click a node for details."
        layout_config = {'name': 'cose', 'idealEdgeLength': 100, 'nodeRepulsion': 50000, 'animate': False, 'fit': True, 'padding': 50} # Reset layout too
        clear_search = ""
        return elements, tap_output_msg, layout_config, clear_search, stylesheet

    elif trigger_id == 'cytoscape-faro-network' and tap_node:
        node_id = tap_node.get('id')
        node_label = tap_node.get('label', 'Unknown')
        if debug_mode: print(f"FARO Node tapped: {node_label} (ID: {node_id})")
        if node_id:
            neighbors_ids = {node_id}
            edges_to_include = []
            neighbor_details_list = []
            for edge in all_edges_base:
                source, target = edge['source'], edge['target']
                other_node_id = None
                if source == node_id and target in node_ids: other_node_id = target
                elif target == node_id and source in node_ids: other_node_id = source
                if other_node_id:
                    neighbors_ids.add(other_node_id)
                    edges_to_include.append(edge)
                    other_node_data = next((n for n in all_nodes_base if n['id'] == other_node_id), None)
                    if other_node_data: neighbor_details_list.append(f"{other_node_data.get('label', other_node_id)} ({other_node_data.get('type', 'N/A')})")

            sub_nodes = [n for n in all_nodes_base if n['id'] in neighbors_ids]
            sub_edges = [e for e in edges_to_include if e['source'] in neighbors_ids and e['target'] in neighbors_ids]
            elements = create_cytoscape_elements(nodes_list=sub_nodes, edges_list=sub_edges, graph_type='faro')

            tap_output_msg_content = [html.H5(f"Focus on: {node_label}")]
            try:
                tapped_details = json.loads(tap_node.get('details_json', '{}')) # Use details_json
                for key, value in tapped_details.items():
                    if value: tap_output_msg_content.append(html.P([html.Strong(f"{key.replace('_', ' ').title()}: "), str(value)], style={'fontSize': '0.9em'}))
            except Exception as e: tap_output_msg_content.append(html.P(f"Error loading details: {e}", style={'color': 'red'}))
            if neighbor_details_list:
                tap_output_msg_content.append(html.P(f"Directly connected to ({len(neighbor_details_list)}):"))
                tap_output_msg_content.append(html.Ul([html.Li(d, style={'fontSize': '0.9em'}) for d in sorted(neighbor_details_list)]))
            tap_output_msg = dbc.Alert(tap_output_msg_content, color="info", style={'maxHeight': '300px', 'overflowY': 'auto'})
            layout_config.update({'name': 'cose', 'padding': 60, 'idealEdgeLength': 150, 'nodeRepulsion': 60000}) # Focused layout
            clear_search = "" # Clear search on click
            return elements, tap_output_msg, layout_config, clear_search, stylesheet

    # Handle Search, Layout, Font Size changes (or initial load)
    if debug_mode: print(f"FARO Handling search/layout/font. Search: '{search_value}', Layout: '{layout_name}', Font: {font_size}")
    filtered_nodes_search = all_nodes_base
    if search_value:
        search_lower = search_value.lower()
        filtered_nodes_search = [n for n in all_nodes_base if search_lower in n['label'].lower()]
    filtered_node_ids_search = {n['id'] for n in filtered_nodes_search}
    filtered_edges_search = [e for e in all_edges_base if e['source'] in filtered_node_ids_search and e['target'] in filtered_node_ids_search]
    elements = create_cytoscape_elements(nodes_list=filtered_nodes_search, edges_list=filtered_edges_search, graph_type='faro')
    tap_output_msg = "Click a node for details."
    if search_value and not elements: tap_output_msg = dbc.Alert(f"No results found for '{search_value}'.", color="warning")
    elif search_value: tap_output_msg = dbc.Alert(f"Showing search results for '{search_value}'. Click node for details.", color="success")
    return elements, tap_output_msg, layout_config, clear_search, stylesheet


# --- Callback for Main Cytoscape Hover ---
@app.callback(
    Output('cytoscape-hover-output', 'children'),
    [Input('cytoscape-faro-network', 'mouseoverNodeData'),
     Input('cytoscape-faro-network', 'mouseoverEdgeData')]
)
def display_main_hover_data(node_data, edge_data):
    try:
        if node_data:
            details = json.loads(node_data.get('details_json', '{}')) # Use details_json
            content = [html.Strong(f"{node_data.get('label', 'Node')} ({node_data.get('type', 'N/A')})")]
            for key, value in details.items():
                 if value and key not in ['details_dict', 'actors', 'color', 'date_parsed', 'actors_str', 'end_date']: # Filter internal/redundant keys
                    display_key = key.replace('_', ' ').title()
                    display_value = str(value)
                    if isinstance(value, str) and len(value) > 150: display_value = value[:150] + "..."
                    elif isinstance(value, list): display_value = ", ".join(map(str, value))
                    content.append(html.P(f"{display_key}: {display_value}", style={'margin': '2px 0', 'fontSize': '0.85em'}))
            return content
        elif edge_data:
            details = json.loads(edge_data.get('details_json', '{}'))
            source, target, label = edge_data.get('source', '?'), edge_data.get('target', '?'), edge_data.get('label', 'related to')
            source_node, target_node = next((n for n in all_nodes_base if n['id'] == source), None), next((n for n in all_nodes_base if n['id'] == target), None)
            source_label, target_label = (source_node['label'] if source_node else source), (target_node['label'] if target_node else target)
            desc = ""
            if edge_data.get('edge_type') == 'causal': desc = f" ({details.get('description', '')})"
            elif edge_data.get('edge_type') == 'shared_event': shared_list = details.get('shared_events', []); desc = f" - Events: {', '.join(shared_list[:5])}{'...' if len(shared_list) > 5 else ''}"
            elif edge_data.get('edge_type') == 'participation': desc = "" # No extra desc needed

            return [html.Strong("Relationship:"), html.Br(), f"{source_label} → {label} → {target_label}{desc}"]
        return "Hover over a node or edge."
    except Exception as e: print(f"Error in main hover display: {e}"); return "Error displaying hover data."


# --- Callbacks for Timeline Tab ---
@app.callback(
    [Output('timeline-graph', 'figure'),
     Output('event-details', 'children'),
     Output('timeline-table', 'data')],
    [Input('event-type-dropdown', 'value'),
     Input('date-range-picker', 'start_date'),
     Input('date-range-picker', 'end_date'),
     Input('timeline-graph', 'clickData')],
    [State('timeline-table', 'data')]
)
def update_timeline(selected_types, start_date_str, end_date_str, click_data, table_data_state):
    ctx = dash.callback_context
    trigger_id = ctx.triggered[0]['prop_id'].split('.')[0] if ctx.triggered else 'initial_load'
    filtered_df = timeline_df.copy()
    if selected_types: filtered_df = filtered_df[filtered_df['type'].isin(selected_types)]
    if start_date_str and end_date_str:
        try:
            start_date, end_date = pd.to_datetime(start_date_str).normalize(), pd.to_datetime(end_date_str).normalize()
            filtered_df = filtered_df[(filtered_df['date_parsed'] >= start_date) & (filtered_df['date_parsed'] <= end_date)]
        except Exception as e: print(f"Date parsing/filtering error: {e}")
    fig = create_timeline_figure(filtered_df)
    table_data = filtered_df[['date_str', 'title', 'type', 'location', 'actors_str']].to_dict('records')
    event_details_children = dbc.Alert("Click an event bubble in the timeline.", color="info")
    if trigger_id == 'timeline-graph' and click_data:
        try:
            event_title = click_data['points'][0]['hovertext']
            event_data = events_df[events_df['title'] == event_title]
            if not event_data.empty:
                row = event_data.iloc[0]
                preceded_by = causal_links_df[causal_links_df['target_event'] == event_title]['source_event'].tolist()
                led_to = causal_links_df[causal_links_df['source_event'] == event_title]['target_event'].tolist()
                event_details_children = dbc.Card([dbc.CardHeader(html.H5(row['title'])), dbc.CardBody([html.P([html.Strong("Date: "), row['date']]), html.P([html.Strong("Location: "), row['location']]), html.P([html.Strong("Type: "), row['type']]), html.P([html.Strong("Actors: "), ", ".join(row['actors'])]), html.H6("Summary:"), html.P(row['summary']), html.H6("Causal Context:", style={'marginTop':'10px'}), html.P([html.Strong("Preceded by: "), ", ".join(preceded_by) or "None"]), html.P([html.Strong("Leads to: "), ", ".join(led_to) or "None"]), ])], outline=True, color="light", className="mb-3")
            else: event_details_children = dbc.Alert(f"Details not found for event: {event_title}", color="warning")
        except Exception as e: print(f"Error extracting event details from click: {e}"); traceback.print_exc(); event_details_children = dbc.Alert(f"Error loading event details: {str(e)}", color="danger")
    return fig, event_details_children, table_data


# --- Callbacks for Actor Tab ---
@app.callback(
    [Output('actor-network-container', 'style'),
     Output('actor-table-container', 'style'),
     Output('actor-details', 'children'),
     Output('cytoscape-actor-network', 'elements'),
     Output('cytoscape-actor-network', 'layout'),
     Output('actor-search-input', 'value'),
     Output('cytoscape-actor-network', 'stylesheet')],
    [Input('actor-view-toggle', 'value'),
     Input('cytoscape-actor-network', 'tapNodeData'),
     Input('actors-table', 'selected_rows'),
     Input('reset-actor-btn', 'n_clicks'),
     Input('cytoscape-actor-layout-dropdown', 'value'),
     Input('actor-search-input', 'value'),
     Input('actor-font-size-slider', 'value')],
    [State('actors-table', 'data')]
)
def update_actor_view_and_cytoscape(view_option, cyto_tap_node, table_selected_rows, reset_clicks, layout_name, search_value, font_size, table_data):
    network_style = {'display': 'block'} if view_option == 'network' else {'display': 'none'}
    table_style = {'display': 'block'} if view_option == 'table' else {'display': 'none'}
    actor_details_children = dbc.Alert("Click an actor node or select a table row.", color="info")
    actor_name = None
    clear_search = dash.no_update # Only clear search on reset or click

    ctx = dash.callback_context
    triggered_prop_id = ctx.triggered[0]['prop_id'] if ctx.triggered else 'initial_load'
    trigger_id = triggered_prop_id.split('.')[0]

    # Determine selected actor name and clear search if needed
    try:
        if trigger_id == 'cytoscape-actor-network' and cyto_tap_node:
            actor_name = cyto_tap_node.get('id'); clear_search = ""
        elif trigger_id == 'actors-table' and table_selected_rows:
            selected_row_index = table_selected_rows[0]
            actor_name = table_data[selected_row_index]['Name']; clear_search = ""
        elif trigger_id == 'reset-actor-btn':
             actor_name = None; clear_search = ""
    except Exception as e: print(f"Error determining selected actor: {e}"); actor_details_children = dbc.Alert(f"Error identifying selected actor: {e}", color="danger")

    # Update Actor Details Panel
    if actor_name:
        try: # Logic remains the same as before
            match_ind = individuals_df[individuals_df['name'] == actor_name]; match_act = actors_df[actors_df['name'] == actor_name]
            if not match_ind.empty:
                ind = match_ind.iloc[0]; events = ind.get('events', [])
                actor_details_children = dbc.Card([ dbc.CardHeader(html.H5(ind['name'])), dbc.CardBody([ html.P([html.Strong("Type: "), f"Individual ({ind.get('role', 'N/A')})"]), html.P([html.Strong("Description: "), ind.get('description', 'N/A')]), html.P([html.Strong("Involvement: "), ind.get('involvement', 'N/A')]), html.H6("Events:", style={'marginTop': '10px'}), html.Ul([html.Li(e) for e in events]) if events else html.P("None") ]) ], outline=True, color="light")
            elif not match_act.empty:
                act = match_act.iloc[0]; events = act.get('events', [])
                actor_details_children = dbc.Card([ dbc.CardHeader(html.H5(act['name'])), dbc.CardBody([ html.P([html.Strong("Type: "), act.get('type', 'N/A')]), html.P([html.Strong("Role: "), act.get('role', 'N/A')]), html.H6("Events:", style={'marginTop': '10px'}), html.Ul([html.Li(e) for e in events]) if events else html.P("None") ]) ], outline=True, color="light")
            else: actor_details_children = dbc.Alert(f"Details not found for {actor_name}", color="warning")
        except Exception as e: print(f"Error creating actor details card: {e}"); actor_details_children = dbc.Alert(f"Error loading actor details: {str(e)}", color="danger")

    # --- Update Actor Cytoscape Elements, Layout, and Stylesheet ---
    layout_config = {'name': layout_name or 'cose', 'animate': False, 'fit': True, 'padding': 50}
    if layout_name == 'concentric': layout_config['levelWidth'] = lambda nodes: 2
    elif layout_name == 'cose': layout_config.update({'idealEdgeLength': 150, 'nodeRepulsion': 70000})

    stylesheet = update_stylesheet_font_size(default_stylesheet, font_size or 10)
    elements = []
    current_search = search_value if clear_search == dash.no_update else ""

    if view_option == 'network':
        # Priority: Reset > Click > Search > Load/Layout Change
        if trigger_id == 'reset-actor-btn':
             if debug_mode: print("Actor Cyto: Resetting graph.")
             elements = create_cytoscape_elements(graph_type='actor')
             layout_config = {'name': 'cose', 'idealEdgeLength': 150, 'nodeRepulsion': 70000, 'animate': False, 'fit': True, 'padding': 50} # Reset layout too

        elif actor_name and trigger_id == 'cytoscape-actor-network': # Subgraph on click
            if debug_mode: print(f"Actor Cyto: Creating subgraph for {actor_name}")
            neighbors_ids = {actor_name}
            edges_to_include = []
            for edge in actor_actor_edges_cy:
                 if edge['source'] == actor_name: neighbors_ids.add(edge['target']); edges_to_include.append(edge)
                 elif edge['target'] == actor_name: neighbors_ids.add(edge['source']); edges_to_include.append(edge)
            sub_nodes = [n for n in actor_individual_nodes_cy if n['id'] in neighbors_ids]
            elements = create_cytoscape_elements(nodes_list=sub_nodes, edges_list=edges_to_include, graph_type='actor')
            layout_config.update({'name': 'concentric', 'padding': 70}) # Focus layout

        elif trigger_id == 'actor-search-input' and current_search: # Filtered graph on search trigger
             if debug_mode: print(f"Actor Cyto: Filtering graph for search '{current_search}'")
             search_lower = current_search.lower()
             filtered_nodes = [n for n in actor_individual_nodes_cy if search_lower in n['label'].lower()]
             filtered_node_ids = {n['id'] for n in filtered_nodes}
             filtered_edges = [e for e in actor_actor_edges_cy if e['source'] in filtered_node_ids and e['target'] in filtered_node_ids]
             elements = create_cytoscape_elements(nodes_list=filtered_nodes, edges_list=filtered_edges, graph_type='actor')
             if not elements: actor_details_children = dbc.Alert(f"No actors match '{current_search}'.", color="warning")

        else: # Full graph (potentially filtered by existing search term if layout/font changed)
            if debug_mode: print(f"Actor Cyto: Creating full graph (Search: '{current_search}').")
            nodes_to_use = actor_individual_nodes_cy
            if current_search: # Apply existing search if present
                 search_lower = current_search.lower()
                 nodes_to_use = [n for n in actor_individual_nodes_cy if search_lower in n['label'].lower()]
            filtered_node_ids = {n['id'] for n in nodes_to_use}
            edges_to_use = [e for e in actor_actor_edges_cy if e['source'] in filtered_node_ids and e['target'] in filtered_node_ids]
            elements = create_cytoscape_elements(nodes_list=nodes_to_use, edges_list=edges_to_use, graph_type='actor')

    # If table view is active, return empty elements/preset layout
    elif view_option == 'table':
        elements = []
        layout_config = {'name': 'preset'}

    return network_style, table_style, actor_details_children, elements, layout_config, clear_search, stylesheet


# --- Callback for Actor Cytoscape Hover ---
@app.callback(
    Output('cytoscape-actor-hover-output', 'children'),
    Input('cytoscape-actor-network', 'mouseoverNodeData'),
    Input('cytoscape-actor-network', 'mouseoverEdgeData'),
    prevent_initial_call=True
)
def display_actor_cyto_hover(node_data, edge_data):
    try:
        if node_data:
            details = json.loads(node_data.get('details_json', '{}')) # Use details_json
            content = [html.Strong(f"{node_data.get('label', 'Actor')} ({node_data.get('type', 'N/A')})")]
            role_desc = details.get('role') or details.get('description') # Get role/desc from details
            if role_desc: content.append(html.P(f"Role/Desc: {role_desc}", style={'margin': '2px 0', 'fontSize': '0.85em'}))
            return content
        elif edge_data:
            details = json.loads(edge_data.get('details_json', '{}'))
            source, target, label = edge_data.get('source', '?'), edge_data.get('target', '?'), edge_data.get('label', 'related')
            shared_events = details.get('shared_events', []) # Get shared events from details
            desc = f" - Shared Events ({len(shared_events)}): {', '.join(shared_events[:5])}{'...' if len(shared_events) > 5 else ''}"
            return [html.Strong("Link (Shared Events):"), html.Br(), f"{source} ↔︎ {target}", html.Br(), html.Small(desc)]
        return "Hover over an actor/individual node or link."
    except Exception as e: print(f"Error in actor hover display: {e}"); return "Error displaying hover data."


# --- Callback for Causal Graph Layout & Font Size (Tab 4) ---
@app.callback(
    [Output('cytoscape-causal-graph', 'layout'),
     Output('cytoscape-causal-graph', 'stylesheet')],
    [Input('cytoscape-causal-layout-dropdown', 'value'),
     Input('reset-causal-layout', 'n_clicks'),
     Input('causal-font-size-slider', 'value')]
)
def update_causal_graph_display(layout_value, reset_clicks, font_size):
    ctx = dash.callback_context
    triggered_prop_id = ctx.triggered[0]['prop_id'] if ctx.triggered else 'initial_load'
    trigger_id = triggered_prop_id.split('.')[0]

    # Determine layout name
    layout_name = 'dagre' # Default
    if trigger_id == 'reset-causal-layout': layout_name = 'dagre'
    elif trigger_id == 'cytoscape-causal-layout-dropdown': layout_name = layout_value or 'dagre'

    # Configure layout
    layout_config = {'name': layout_name, 'animate': False, 'fit': True, 'padding': 50} # Increased padding
    if layout_name == 'dagre': layout_config.update({'rankDir': 'TB', 'rankSep': 120, 'nodeSep': 100}) # Spacing for better centering attempt
    elif layout_name == 'cose': layout_config.update({'idealEdgeLength': 150, 'nodeRepulsion': 40000})
    elif layout_name == 'breadthfirst': layout_config.update({'roots': '#Ukraine Drops EU Deal; Protests Begin (Euromaidan)', 'spacingFactor': 1.8})
    elif layout_name == 'circle': layout_config.update({'radius': 350}) # Example adjustment

    # Update stylesheet with font size
    stylesheet = update_stylesheet_font_size(default_stylesheet, font_size or 10)

    if debug_mode: print(f"Updating causal graph: Layout='{layout_name}', Font Size='{font_size}px'")
    return layout_config, stylesheet

# ------------------------------------------------------------------------------
# RUN THE APPLICATION
# ------------------------------------------------------------------------------
if __name__ == '__main__':
    print("Attempting to start Dash server...")
    print(f"Current Working Directory: {os.getcwd()}")
    assets_folder = os.path.join(os.getcwd(), 'assets')
    if not os.path.isdir(assets_folder): print(f"Warning: 'assets' folder not found at {assets_folder}. Logos may not display.")
    else: print(f"Assets folder found at: {assets_folder}")
    app.run(debug=debug_mode, host='0.0.0.0', port=8052)
    