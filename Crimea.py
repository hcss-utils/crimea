import pandas as pd
import numpy as np
import json
from datetime import datetime, date
import re
import dash
# import dash_mantine_components as dmc
from dash import Dash, html
from dash import dcc, html, dash_table
from dash.dependencies import Input, Output, State, ALL
import dash_bootstrap_components as dbc
import plotly.express as px
import plotly.graph_objects as go
import networkx as nx
import dash_cytoscape as cyto  # Import Cytoscape
import os
import traceback
import uuid  # For Cytoscape element generation if needed

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
            if debug_mode: print(f"DEBUG (parse_date): Parsed simple range: '{original_date_str}' -> '{date_str}'")

        # Complex range match: "22 Apr - 3 May 2014" -> use the first day
        range_match_complex = re.match(r"(\d{1,2}\s+\w{3})\s*-\s*\d{1,2}\s+\w{3}\s+(\d{4})", date_str)
        if range_match_complex:
            day_month_start, year = range_match_complex.groups()
            date_str = f"{day_month_start} {year}"
            if debug_mode: print(f"DEBUG (parse_date): Parsed complex range: '{original_date_str}' -> '{date_str}'")

        formats_to_try = ["%d %b %Y"]
        parsed_date = None
        for fmt in formats_to_try:
            try:
                parsed_date = datetime.strptime(date_str, fmt)
                # if debug_mode: print(f"DEBUG (parse_date): Successfully parsed '{date_str}' with format '{fmt}'")
                return parsed_date # Success
            except ValueError:
                continue # Try next format

        # Fallback if formats failed
        print(f"Warning: Could not parse date string '{original_date_str}' (processed as '{date_str}') with known formats.")
        return datetime(2014, 2, 27) # Default fallback

    except Exception as e:
        print(f"Error during date parsing for: '{original_date_str}', Processed str: '{date_str}'. Error: {e}")
        # traceback.print_exc() # Uncomment for full traceback if needed
        return datetime(2014, 2, 27) # Default fallback
    
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
    {"name": "Sergey Aksyonov (Crimea PM)", "type": "Regional Leader (De Facto)", "role": "Issued ban on mass gatherings.", "events": ["Defying Ban, Tatars Commemorate Deportation Anniversary"]},
    {"name": "Petro Poroshenko", "type": "Individual", "role": "President of Ukraine from 7 Jun 2014", "events": ["New Ukrainian President Elected, Vows to Reclaim Crimea"]},
    {"name": "Ukrainian voters", "type": "Group (Civil)", "role": "Elected Poroshenko.", "events": ["New Ukrainian President Elected, Vows to Reclaim Crimea"]},
    {"name": "Russian gov't", "type": "National Government", "role": "Government opposing Poroshenko's stance.", "events": ["New Ukrainian President Elected, Vows to Reclaim Crimea"]}
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

# ------------------------------------------------------------------------------
# DataFrame conversions and timeline preparation
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

# ------------------------------------------------------------------------------
# Node and edge definitions for visualization
# ------------------------------------------------------------------------------
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

# Define node type options for filter checklist dynamically
unique_node_types = sorted(list(set(n['type'] for n in all_nodes)))
node_type_options = [{'label': nt, 'value': nt} for nt in unique_node_types]

# Manually define edge type options
edge_type_options = [
    {'label': 'Causal Links', 'value': 'causal'},
    {'label': 'Participation Links', 'value': 'participation'}
]

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

# Stylesheet for Cytoscape
default_stylesheet = [
    {'selector': 'node', 'style': {
        'label': 'data(label)',
        'font-size': '10px',
        'width': 'mapData(size, 5, 30, 5, 30)', # Map node size data property to width
        'height': 'mapData(size, 5, 30, 5, 30)', # Map node size data property to height
        'text-valign': 'bottom',
        'text-halign': 'center',
        'text-margin-y': '6px',
        'border-width': 1,
        'border-color': '#555'
    }},
    # Node type specific styles
    {'selector': '.Event', 'style': {'background-color': node_types['Event'], 'shape': 'ellipse'}},
    {'selector': '.Country', 'style': {'background-color': node_types['Country'], 'shape': 'rectangle'}},
    {'selector': '.Organization', 'style': {'background-color': node_types['Organization'], 'shape': 'rectangle'}},
    {'selector': '.Individual', 'style': {'background-color': node_types['Individual'], 'shape': 'diamond'}},
    {'selector': '.Actor', 'style': {'background-color': node_types['Actor'], 'shape': 'rectangle'}}, # Fallback Actor style

    # Edge type specific styles
    {'selector': 'edge', 'style': {
        'label': 'data(label)',
        'font-size': '8px',
        'curve-style': 'bezier', # Or 'straight', 'haystack', etc.
        'width': 'mapData(width, 1, 3, 1, 3)' # Map edge width data property
    }},
    {'selector': '.causal', 'style': { # Style for causal edges
        'line-color': '#333',
        'target-arrow-shape': 'triangle',
        'target-arrow-color': '#333'
    }},
    {'selector': '.participation', 'style': { # Style for participation edges
        'line-color': '#999',
        'line-style': 'dashed',
        'target-arrow-shape': 'tee',
        'target-arrow-color': '#999'
    }},

    # Styles for selected/hovered elements
    {'selector': 'node:selected', 'style': {
        'border-width': 3, 'border-color': 'black', 'border-opacity': 1, 'opacity': 1, 'z-index': 9999
    }},
    {'selector': 'edge:selected', 'style': {
        'width': 4, 'line-color': 'black', 'opacity': 1, 'z-index': 9998
    }},
     {'selector': 'node:hover', 'style': {
        'border-width': 3, 'border-color': '#666', 'border-opacity': 1, 'opacity': 1
    }},
    {'selector': 'edge:hover', 'style': {
        'width': 3, 'line-color': '#666', 'opacity': 1
    }}
]

def create_cytoscape_elements(view_option='full', search_text="", node_type_filters=None, edge_type_filters=None):
    """
    Generate Cytoscape elements based on the view option and search filter.
    Handles 'full', 'events', 'actors', 'russia', 'international', 'causal_only'.
    """
    if debug_mode:
        print(f"Creating Cytoscape elements with view_option={view_option}, search_text='{search_text}'")

    # Set defaults if filters are None
    if node_type_filters is None:
        node_type_filters = unique_node_types
    if edge_type_filters is None:
        edge_type_filters = [opt['value'] for opt in edge_type_options]
        
    # Determine initial set based on view_option
    filtered_nodes_data = []
    filtered_edges_data = []
    node_ids_in_view = set()

    if view_option == 'full':
        filtered_nodes_data = all_nodes
        filtered_edges_data = all_edges
        node_ids_in_view = {n['id'] for n in filtered_nodes_data}
    elif view_option == 'events':
        filtered_nodes_data = [n for n in all_nodes if n['type'] == "Event"]
        node_ids_in_view = {n['id'] for n in filtered_nodes_data}
        filtered_edges_data = [e for e in causal_edges if e['source'] in node_ids_in_view and e['target'] in node_ids_in_view]
    elif view_option == 'causal_only': # *** Specific view for causal graph ***
        if debug_mode: print(f"Filtering for causal_only view.")
        filtered_nodes_data = [n for n in all_nodes if n['type'] == "Event"]
        node_ids_in_view = {n['id'] for n in filtered_nodes_data}
        filtered_edges_data = [e for e in causal_edges if e['source'] in node_ids_in_view and e['target'] in node_ids_in_view]
    elif view_option == 'actors':
        actor_related_nodes = [n for n in all_nodes if n['type'] in ["Actor", "Individual", "Country", "Organization"]]
        actor_ids = {n['id'] for n in actor_related_nodes}
        linked_event_ids = set()
        relevant_participation_edges = []
        for edge in actor_event_edges + individual_event_edges:
             # Edges from Actor/Individual to Event
            if edge['source'] in actor_ids and edge['target'] in event_titles:
                linked_event_ids.add(edge['target'])
                relevant_participation_edges.append(edge)
            # Edges from Event to Actor/Individual (less common, but possible)
            elif edge['target'] in actor_ids and edge['source'] in event_titles:
                 linked_event_ids.add(edge['source'])
                 relevant_participation_edges.append(edge)
        event_subset = [n for n in event_nodes if n['id'] in linked_event_ids]
        filtered_nodes_data = actor_related_nodes + event_subset
        node_ids_in_view = {n['id'] for n in filtered_nodes_data}
        filtered_edges_data = [e for e in relevant_participation_edges if e['source'] in node_ids_in_view and e['target'] in node_ids_in_view]
         # Optionally add actor-actor links here if needed, based on shared events etc.
    elif view_option == 'russia':
        russia_focus_ids = { "Russia (Russian Federation)", "Vladimir Putin", "Sergey Aksyonov", "Crimean Supreme Council (Parliament)", "Russian Armed Forces (Black Sea Fleet)", "Crimean 'Self-Defense' Forces", "Russian Federation Council", "Russian State Duma & Federation Council", "Russian Parliament", "Unmarked Russian special forces", "Crimean gov't (Aksyonov)", "Aleksei Chaly", "Russian Unity party", "Russian gov't" }
        node_ids_in_view.update(russia_focus_ids)
        nodes_to_add = set(node_ids_in_view)
        edges_to_add_tuples = set() # Use set of tuples to avoid duplicate edges
        for edge in all_edges:
            source_in = edge['source'] in node_ids_in_view
            target_in = edge['target'] in node_ids_in_view
            if source_in and target_in:
                 edges_to_add_tuples.add( (edge['source'], edge['target']) )
            elif source_in and not target_in:
                 nodes_to_add.add(edge['target']) # Add neighbor node
                 edges_to_add_tuples.add( (edge['source'], edge['target']) )
            elif target_in and not source_in:
                 nodes_to_add.add(edge['source']) # Add neighbor node
                 edges_to_add_tuples.add( (edge['source'], edge['target']) )
        filtered_nodes_data = [n for n in all_nodes if n['id'] in nodes_to_add]
        node_ids_in_view = nodes_to_add # Update with added neighbors
        filtered_edges_data = [e for e in all_edges if (e['source'], e['target']) in edges_to_add_tuples or (e['target'], e['source']) in edges_to_add_tuples] # Check both directions if undirected conceptually needed
        # Refilter edges to be strictly between nodes now in view
        filtered_edges_data = [e for e in filtered_edges_data if e['source'] in node_ids_in_view and e['target'] in node_ids_in_view]

    elif view_option == 'international':
        intl_focus_ids = { "United States", "European Union (EU) and G7", "United Nations", "NATO (North Atlantic Treaty Organization)", "OSCE (Organization for Security & Co-operation in Europe)", "Barack Obama", "G7 (USA, UK, France, Germany, Italy, Canada, Japan) & EU", "UN General Assembly (193 member states)", "United Nations Security Council (P5: Russia, US, UK, France, China)", "USA", "EU" }
        node_ids_in_view.update(intl_focus_ids)
        nodes_to_add = set(node_ids_in_view)
        edges_to_add_tuples = set()
        for edge in all_edges:
            source_in = edge['source'] in node_ids_in_view
            target_in = edge['target'] in node_ids_in_view
            if source_in and target_in:
                 edges_to_add_tuples.add( (edge['source'], edge['target']) )
            elif source_in and not target_in:
                 nodes_to_add.add(edge['target'])
                 edges_to_add_tuples.add( (edge['source'], edge['target']) )
            elif target_in and not source_in:
                 nodes_to_add.add(edge['source'])
                 edges_to_add_tuples.add( (edge['source'], edge['target']) )
        filtered_nodes_data = [n for n in all_nodes if n['id'] in nodes_to_add]
        node_ids_in_view = nodes_to_add
        filtered_edges_data = [e for e in all_edges if (e['source'], e['target']) in edges_to_add_tuples or (e['target'], e['source']) in edges_to_add_tuples]
        filtered_edges_data = [e for e in filtered_edges_data if e['source'] in node_ids_in_view and e['target'] in node_ids_in_view]

    else: # Default to full view if option not recognized
        filtered_nodes_data = all_nodes
        filtered_edges_data = all_edges
        node_ids_in_view = {n['id'] for n in filtered_nodes_data}

    # --- Apply search filter if provided, AFTER view filter ---
    if search_text:
        if debug_mode: print(f"Applying search filter: '{search_text}'")
        search_text_lower = search_text.lower()
        # Filter nodes based on search text
        original_node_count = len(filtered_nodes_data)
        filtered_nodes_data = [node for node in filtered_nodes_data if search_text_lower in node['label'].lower()]
        if debug_mode: print(f"Nodes filtered by search: {original_node_count} -> {len(filtered_nodes_data)}")
        # Update the set of node IDs that are currently in view after search
        node_ids_in_view = {node['id'] for node in filtered_nodes_data}
        # Filter edges to only include those connecting the remaining nodes
        original_edge_count = len(filtered_edges_data)
        filtered_edges_data = [edge for edge in filtered_edges_data if edge['source'] in node_ids_in_view and edge['target'] in node_ids_in_view]
        if debug_mode: print(f"Edges filtered by search: {original_edge_count} -> {len(filtered_edges_data)}")

    # --- Apply Node Type filter ---
    if node_type_filters and node_type_filters != unique_node_types:
        original_node_count = len(filtered_nodes_data)
        filtered_nodes_data = [node for node in filtered_nodes_data if node['type'] in node_type_filters]
        if debug_mode: print(f"Nodes filtered by type: {original_node_count} -> {len(filtered_nodes_data)}")
        # Update node IDs in view
        node_ids_in_view = {node['id'] for node in filtered_nodes_data}
        # Refilter edges
        original_edge_count = len(filtered_edges_data)
        filtered_edges_data = [edge for edge in filtered_edges_data if edge['source'] in node_ids_in_view and edge['target'] in node_ids_in_view]
        if debug_mode: print(f"Edges refiltered after node type: {original_edge_count} -> {len(filtered_edges_data)}")

    # --- Apply Edge Type filter ---
    if edge_type_filters and len(edge_type_filters) < len(edge_type_options):
        original_edge_count = len(filtered_edges_data)
        filtered_edges_data = [edge for edge in filtered_edges_data if edge['type'] in edge_type_filters]
        if debug_mode: print(f"Edges filtered by type: {original_edge_count} -> {len(filtered_edges_data)}")

    # --- Convert filtered nodes/edges to Cytoscape element format ---
    elements = []
    for node in filtered_nodes_data:
        details = {k: v for k, v in node.items() if k not in ['id', 'label', 'color']}
        node_data_cy = {
            'id': node['id'],
            'label': node['label'],
            'type': node['type'], # Main type for potential use
            'size': 25 if node['type'] == 'Event' else (15 if node['type'] == 'Individual' else 20), # Size based on main type
            'details': json.dumps(details) # Store all other details as JSON string
        }
        # Determine class for styling based on detailed type/category
        node_class = node['type'] # Default
        category = node.get('category', '')
        if "Country" in category: node_class = "Country"
        elif any(sub in category for sub in ["Organization", "Union", "Military Alliance", "International Body", "Legislative Body", "State Force", "Military", "Paramilitary", "Group", "Party", "Community", "Government"]): node_class = "Organization"
        elif node['type'] == 'Individual': node_class = "Individual"
        elif node['type'] == 'Event': node_class = "Event"
        # Add other specific types if needed, e.g., Actor might need refinement
        elif node['type'] == 'Actor' and not category: node_class = "Actor" # Use Actor if no category specified

        elements.append({'data': node_data_cy, 'classes': node_class}) # Use detailed type for class

    for edge in filtered_edges_data:
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
        print(f"Final elements count: {len(elements)} ({len([e for e in elements if 'source' not in e['data']])} nodes, {len([e for e in elements if 'source' in e['data']])} edges)")

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
                    title_font_size=16,
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
        # TAB 1: FARO Knowledge Graph
        dbc.Tab(label="FARO Knowledge Graph", tab_id="tab-1", children=[
            dbc.Row([
                dbc.Col([
                    html.H3("FARO Ontology Network (Cytoscape)",
                            style={'textAlign': 'center', 'marginTop': '20px'}),
                    html.P("Interactive network of events, actors, and relationships. Hover for detailed tooltips. Click a node to focus on its subgraph details.",
                           style={'textAlign': 'center', 'marginBottom': '20px'})
                ], width=12)
            ]),
            dbc.Row([
                dbc.Col([
                    html.Label("Select Layout:"),
                    dcc.Dropdown(
                        id='cytoscape-layout-dropdown',
                        options=[
                            {'label': 'Cose (Force Directed)', 'value': 'cose'},
                            {'label': 'Grid', 'value': 'grid'},
                            {'label': 'Circle', 'value': 'circle'},
                            {'label': 'Breadthfirst', 'value': 'breadthfirst'},
                            {'label': 'Dagre', 'value': 'dagre'}
                        ],
                        value='cose',
                        clearable=False
                    )
                ], width=4, md=3),
                dbc.Col([
                    html.Label("Search Nodes:"),
                    dcc.Input(id="cytoscape-search-input", type="text", placeholder="Type to search...", style={"width": "100%"})
                ], width=4, md=3),
                dbc.Col([
                    html.Button("Reset Graph", id="reset-btn", n_clicks=0, className="btn btn-secondary", style={"marginTop": "28px"})
                ], width=4, md=3)
            ], justify="center", style={'marginBottom': '20px'}),
            dbc.Row([
                dbc.Col([
                    dcc.Loading(id="loading-cytoscape", type="circle", children=[
                        cyto.Cytoscape(
                            id='cytoscape-faro-network',
                            elements=create_cytoscape_elements('full'),
                            layout={'name': 'cose', 'animate': True},
                            style={'width': '100%', 'height': '750px', 'border': '1px solid #ddd'},
                            stylesheet=default_stylesheet
                        )
                    ])
                ], width=12)
            ]),
            dbc.Row([
                dbc.Col([
                    html.Div(id='cytoscape-hover-output', style={
                        'marginTop': '10px',
                        'padding': '10px',
                        'border': '1px solid #ccc',
                        'borderRadius': '5px',
                        'fontSize': '18px',
                        'minHeight': '60px'
                    }, children="Hover over a node or edge to see details."),
                    html.Div(id='cytoscape-tapNodeData-output', style={
                        'marginTop': '20px',
                        'padding': '10px',
                        'border': '1px dashed #ccc'
                    }, children="Click on a node to see its subgraph details.")
                ], width=12)
            ]),
            dbc.Row([
                dbc.Col([
                    html.H5("Legend:"),
                    dbc.Row([
                        dbc.Col([
                            html.Div([html.Div(style={'backgroundColor': node_types["Event"],
                                                       'width': '20px',
                                                       'height': '20px',
                                                       'display': 'inline-block',
                                                       'marginRight': '5px',
                                                       'border': '1px solid #ccc'}),
                                      html.Span(" Event", style={'verticalAlign': 'middle'})],
                                     style={'marginBottom': '5px'}),
                            html.Div([html.Div(style={'backgroundColor': node_types["Individual"],
                                                       'width': '20px',
                                                       'height': '20px',
                                                       'display': 'inline-block',
                                                       'marginRight': '5px',
                                                       'border': '1px solid #ccc'}),
                                      html.Span(" Individual", style={'verticalAlign': 'middle'})],
                                     style={'marginBottom': '5px'})
                        ], width=6, md=4),
                        dbc.Col([
                            html.Div([html.Div(style={'backgroundColor': node_types["Country"],
                                                       'width': '20px',
                                                       'height': '20px',
                                                       'display': 'inline-block',
                                                       'marginRight': '5px',
                                                       'border': '1px solid #ccc'}),
                                      html.Span(" Country", style={'verticalAlign': 'middle'})],
                                     style={'marginBottom': '5px'}),
                            html.Div([html.Div(style={'backgroundColor': node_types["Organization"],
                                                       'width': '20px',
                                                       'height': '20px',
                                                       'display': 'inline-block',
                                                       'marginRight': '5px',
                                                       'border': '1px solid #ccc'}),
                                      html.Span(" Org/Other", style={'verticalAlign': 'middle'})],
                                     style={'marginBottom': '5px'})
                        ], width=6, md=4)
                    ], justify="center")
                ], width=12)
            ], style={'marginTop': '20px', 'padding': '15px', 'border': '1px solid #ddd', 'backgroundColor': 'rgba(250, 250, 250, 0.9)'})
        ]),
        # TAB 2: Chronological Event Timeline
        dbc.Tab(label="Chronological Event Timeline", tab_id="tab-2", children=[
            dbc.Row([
                dbc.Col([
                    html.H3("Timeline of Key Events",
                            style={'textAlign': 'center', 'marginTop': '20px'}),
                    html.P("Use the dropdown below to filter by event type and the date picker for a custom range.",
                           style={'textAlign': 'center', 'marginBottom': '20px'})
                ], width=12)
            ]),
            dbc.Row([
                dbc.Col([
                    html.Label("Filter by Event Type:"),
                    dcc.Dropdown(
                        id='event-type-dropdown',
                        options=[{'label': t, 'value': t} for t in sorted(timeline_df['type'].unique())],
                        value=[],
                        multi=True,
                        placeholder="Select event types..."
                    )
                ], width=6, md=6),
                dbc.Col([
                    html.Label("Date Range:"),
                    dcc.DatePickerRange(
                        id='date-range-picker',
                        min_date_allowed=timeline_df['date_parsed'].min().date(),
                        max_date_allowed=timeline_df['date_parsed'].max().date(),
                        start_date=timeline_df['date_parsed'].min().date(),
                        end_date=timeline_df['date_parsed'].max().date(),
                        display_format='DD MMM YY'
                    )
                ], width=6, md=6)
            ], justify="center", style={'marginBottom': '20px'}),
            dbc.Row([
                dbc.Col([
                    dcc.Graph(id='timeline-graph', figure=create_timeline_figure(), style={'height': '600px'})
                ], width=12)
            ]),
            dbc.Row([
                dbc.Col([
                    html.H4("Event Details", style={'marginTop': '30px'}),
                    dcc.Loading(id='loading-event-details', type='circle', children=[
                        html.Div(id='event-details', children="Click on an event in the timeline above to see details.")
                    ], style={'marginTop': '10px', 'padding': '15px', 'border': '1px solid #eee', 'minHeight': '100px'})
                ], width=12)
            ]),
            # Add hidden div for storing timeline table data
            html.Div(id='timeline-table', style={'display': 'none'})
        ]),
        # TAB 3: Actors and Roles
        dbc.Tab(label="Actors and Roles", tab_id="tab-3", children=[
            dbc.Row([
                dbc.Col([
                    html.H3("Key Actors", style={'textAlign': 'center', 'marginTop': '20px'}),
                    html.P("Toggle between the relationship network and a detailed table.", style={'textAlign': 'center', 'marginBottom': '20px'}),
                    dbc.RadioItems(
                        id='actor-view-toggle',
                        options=[
                            {'label': 'Relationship Network', 'value': 'network'},
                            {'label': 'Detailed Table', 'value': 'table'}
                        ],
                        value='network',
                        inline=True,
                        style={'textAlign': 'center'}
                    )
                ], width=12)
            ]),
            dbc.Row([
                dbc.Col([
                    html.Div(id='actor-network-container', children=[
                        dcc.Loading(id='loading-actor-network', type='circle', children=[
                            dcc.Graph(id='actor-network-graph', figure=create_actor_relationships(), style={'height': '700px'})
                        ])
                    ], style={'display': 'block'}),
                    html.Div(id='actor-table-container', children=[
                        dash_table.DataTable(
                            id='actors-table',
                            columns=[
                                {'name': 'Name', 'id': 'Name'},
                                {'name': 'Type', 'id': 'Type'},
                                {'name': 'Role/Description', 'id': 'Role/Description'},
                                {'name': 'Events Involved In', 'id': 'Events Involved In'}
                            ],
                            data=create_actors_table().to_dict('records'),
                            style_table={'overflowX': 'auto'},
                            style_header={'backgroundColor': 'rgb(230, 230, 230)', 'fontWeight': 'bold'},
                            style_cell={'textAlign': 'left', 'padding': '10px', 'whiteSpace': 'normal', 'height': 'auto', 'minWidth': '100px', 'width': 'auto', 'maxWidth': '300px'},
                            page_size=15,
                            filter_action="native",
                            sort_action="native",
                            sort_mode="multi",
                            style_data_conditional=[{'if': {'row_index': 'odd'}, 'backgroundColor': 'rgb(248, 248, 248)'}]
                        )
                    ], style={'display': 'none'}),
                    html.Div([
                        html.H4("Actor Details", style={'marginTop': '30px'}),
                        dcc.Loading(id='loading-actor-details', type='circle', children=[
                            html.Div(id='actor-details', children="Select an actor from the network or table above to view details.")
                        ], style={'marginTop': '10px', 'padding': '15px', 'border': '1px solid #eee', 'minHeight': '100px'})
                    ])
                ], width=12)
            ]),
            # Add a hidden div for table loading feedback
            html.Div(id='actor-table-loading-output', style={'display': 'none'})
        ])
# TAB 4: Analysis & Perspectives
        dbc.Tab(label="Analysis & Perspectives", tab_id="tab-4", children=[
            dbc.Tabs([
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
                                    html.H5("Key Turning Points Visualization"),
                                    dbc.Row([
                                        dbc.Col([
                                            html.Label("Select Layout:"),
                                            dcc.Dropdown(
                                                id='cytoscape-causal-layout-dropdown',
                                                options=[
                                                    {'label': 'Breadthfirst', 'value': 'breadthfirst'},
                                                    {'label': 'Cose (Force Directed)', 'value': 'cose'},
                                                    {'label': 'Grid', 'value': 'grid'},
                                                    {'label': 'Circle', 'value': 'circle'},
                                                    {'label': 'Dagre', 'value': 'dagre'}
                                                ],
                                                value='breadthfirst',
                                                clearable=False),
                                            dcc.Graph(
                                                id='causal-flow-chart',
                                                figure=px.scatter(
                                                    events_df.iloc[[0, 2, 5, 9, 12, 13, 17, 19]],
                                                    x='date_parsed',
                                                    y='type',
                                                    text='title',
                                                    size=[20]*8,
                                                    color='type',
                                                    height=400,
                                                    labels={"date_parsed": "Timeline", "type": "Event Category"},
                                                    title="Critical Events in the Annexation Sequence"
                                                ).update_traces(
                                                    mode='markers+text',
                                                    textposition='top center',
                                                    textfont_size=12
                                                ).update_layout(
                                                    yaxis={'visible': True, 'title': 'Event Category'},
                                                    xaxis_title="Timeline",
                                                    showlegend=True,
                                                    legend_title_text='Category',margin=dict(l=20, r=20, t=50, b=100)
                                                )
                                            )
                                        ], width=12, md=6),
                                        dbc.Col([
                                            html.Button("Reset Layout", id="reset-causal-layout", n_clicks=0, className="btn btn-secondary", style={"marginTop": "28px"}),
                                            dcc.Loading(id="loading-cytoscape-causal", type="default", children=[
                                                cyto.Cytoscape(
                                                    id='cytoscape-causal-graph',
                                                    elements=create_cytoscape_elements('causal_only'),
                                                    layout={'name': 'breadthfirst', 'roots': '[id = "Ukraine Drops EU Deal; Protests Begin (Euromaidan)"]', 'spacingFactor': 1.5, 'animate': False},
                                                    style={'width': '100%', 'height': '500px', 'border': '1px solid #ddd'},
                                                    stylesheet=default_stylesheet
                                                )
                                            ])
                                        ], width=12, md=6)
                                    ])
                                ])
                            ], width=12)
                        ])
                    ]
                ),
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
                                        dcc.Graph(
                                            id='un-vote-chart',
                                            figure=px.pie(
                                                names=['In favor (Affirming Ukraine Integrity)', 'Against (Opposing Resolution)', 'Abstentions', 'Non-Voting'],
                                                values=[100, 11, 58, 24],
                                                title="UNGA Vote on Ukraine's Territorial Integrity (Mar 2014)",
                                                color_discrete_sequence=['#4285F4', '#EA4335', '#FBBC05', '#CCCCCC'],
                                                hole=0.3
                                            ).update_traces(textinfo='percent+label')
                                        )
                                    ], width=12, lg=6),
                                    dbc.Col([
                                        html.H5("Initial Sanctions Timeline (Mar-Jul 2014)"),
                                        dcc.Graph(
                                            id='sanctions-timeline',
                                            figure=px.timeline(
                                                pd.DataFrame([
                                                    dict(Sanction="US Initial Individual Sanctions", Start='2014-03-17', Finish='2014-03-20', Actor='US'),
                                                    dict(Sanction="EU Initial Individual Sanctions", Start='2014-03-17', Finish='2014-03-21', Actor='EU'),
                                                    dict(Sanction="G7 Suspends Russia", Start='2014-03-24', Finish='2014-03-25', Actor='G7'),
                                                    dict(Sanction="Expanded Sectoral Sanctions", Start='2014-07-16', Finish='2014-07-31', Actor='US/EU')
                                                ]),
                                                x_start="Start",
                                                x_end="Finish",
                                                y="Sanction",
                                                color="Actor",
                                                title="Timeline of Early Western Sanctions",
                                                labels={"Sanction": "Sanction Type/Action"}
                                            ).update_yaxes(
                                                categoryorder='array',
                                                categoryarray=[
                                                    "Expanded Sectoral Sanctions",
                                                    "G7 Suspends Russia",
                                                    "EU Initial Individual Sanctions",
                                                    "US Initial Individual Sanctions"
                                                ]
                                            )
                                        )
                                    ], width=12, lg=6)
                                ]),
                                html.H5("Key Response Patterns:", style={'marginTop': '30px'}),
                                html.Ul([
                                    html.Li("Diplomatic condemnation and legal resolutions."),
                                    html.Li("Economic sanctions and asset freezes."),
                                    html.Li("Actions by international organizations."),
                                    html.Li("Avoidance of direct military confrontation."),
                                    html.Li("Long-term strategic isolation of Russia.")
                                ])
                            ], width=12)
                        ])
                    ]
                ),
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
                                        html.Ul([
                                            html.Li([html.Strong("UN Charter:"), " Prohibition against the use of force to alter borders."]),
                                            html.Li([html.Strong("Helsinki Final Act (1975):"), " Inviolability of frontiers."]),
                                            html.Li([html.Strong("Budapest Memorandum (1994):"), " Pledges to respect Ukraine's sovereignty."]),
                                            html.Li([html.Strong("Russia-Ukraine Friendship Treaty (1997):"), " Explicit recognition of Crimea as part of Ukraine."]),
                                            html.Li([html.Strong("Ukrainian Constitution:"), " Requires national referendum for territorial changes."])
                                        ]),
                                        html.H5("Russian Justifications / Counterarguments:", style={'marginTop': '15px'}),
                                        html.Ul([
                                            html.Li("Protection of Russian speakers."),
                                            html.Li("Right to self-determination."),
                                            html.Li("Alleged invitation from a deposed leader."),
                                            html.Li("Correction of historical injustice.")
                                        ])
                                    ], width=12, lg=6),
                                    dbc.Col([
                                        html.H5("Territorial Impact - Crimea Profile"),
                                        dbc.Card(
                                            dbc.CardBody([
                                                html.P([html.Strong("Area: "), "~27,000 km²"]),
                                                html.P([html.Strong("Population (2014 est.): "), "~2.3 million"]),
                                                html.P([html.Strong("Coastline: "), "~1,000 km"]),
                                                html.P([html.Strong("Strategic Importance: "), "Base for Russia's Black Sea Fleet"]),
                                                html.P([html.Strong("Economic Impact: "), "Loss of tourism, port revenue, and international trade."])
                                            ]),
                                            className="mb-3"
                                        ),
                                        html.P(
                                            [html.Strong("Status Discrepancy:"), " Russia administers Crimea despite non-recognition by most nations."],
                                            style={'marginTop': '20px'}
                                        )
                                    ], width=12, lg=6)
                                ]),
                                html.P(
                                    [html.Strong("Lasting Status (as of April 2025):"), " Crimea remains under Russian control, with ongoing legal and diplomatic disputes."],
                                    style={'marginTop': '20px', 'fontWeight': 'bold'}
                                )
                            ], width=12)
                        ])
                    ]
                )
            ],
            id='analysis-subtabs',
            active_tab="analysis-causal"
        ])
    ], id='tabs', active_tab="tab-1"),
    dbc.Row([
        dbc.Col([
            html.Hr(),
            html.P(
                ["Data compiled from open sources.", html.Br(), "Visualization based on FARO ontology."],
                style={'textAlign': 'center', 'marginTop': '20px', 'color': '#666', 'fontSize': '14px'}
            )
        ], width=12)
    ])
], fluid=True, style={'fontFamily': 'Arial, sans-serif'})

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

# Callback for causal graph layout
@app.callback(
    Output('cytoscape-causal-graph', 'layout'),
    Input('cytoscape-causal-layout-dropdown', 'value'),
    prevent_initial_call=True
)
def update_cytoscape_causal_layout(layout_name):
    if debug_mode:
        print(f"Updating causal layout to: {layout_name}")
    
    try:
        layout_config = {'name': layout_name, 'animate': False}  # Disabled animation for better performance
        if layout_name == 'cose':
            layout_config['idealEdgeLength'] = 100
            layout_config['nodeRepulsion'] = 400000
        elif layout_name == 'dagre':
            layout_config['rankDir'] = 'TB'
        elif layout_name == 'breadthfirst':
            layout_config['roots'] = '[id = "Ukraine Drops EU Deal; Protests Begin (Euromaidan)"]'
            layout_config['spacingFactor'] = 1.5
        return layout_config
    except Exception as e:
        return {'name': 'breadthfirst', 'roots': '[id = "Ukraine Drops EU Deal; Protests Begin (Euromaidan)"]', 'spacingFactor': 1.5, 'animate': False}

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
     Output('cytoscape-tapNodeData-output', 'children')],
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

    # Determine which input triggered the callback
    if not ctx.triggered:
        trigger_id = 'initial_load'
    else:
        trigger_id = ctx.triggered[0]['prop_id'].split('.')[0]

    try:
        # Handle Reset Button Click
        if trigger_id == 'reset-btn':
            if debug_mode: print("Reset button clicked")
            elements = create_cytoscape_elements('full', search_text=search_value or "")
            tap_output_msg = "Graph has been reset. Click on a node to see its subgraph details."
            return elements, tap_output_msg

        # Handle Node Tap
        elif trigger_id == 'cytoscape-faro-network' and tap_node:
            if debug_mode: print(f"Node tapped: {tap_node.get('label', 'Unknown')}")
            
            # Get the node ID and label
            node_id = tap_node.get('id')
            node_label = tap_node.get('label', 'Unknown')
            
            if not node_id:
                raise ValueError("Tapped node has no ID!")
            
            # Find all connected edges and neighbor nodes
            neighbors = {node_id}  # Include the tapped node
            neighbor_details_list = []
            
            # Find direct connections
            for edge in all_edges:
                if edge['source'] == node_id:
                    neighbors.add(edge['target'])
                    # Get target node's info for display
                    target_nodes = [n for n in all_nodes if n['id'] == edge['target']]
                    if target_nodes:
                        target_type = target_nodes[0].get('type', 'Unknown')
                        target_label = target_nodes[0].get('label', edge['target'])
                        neighbor_details_list.append(f"{target_label} ({target_type}) - {edge.get('label', 'connected to')}")
                elif edge['target'] == node_id:
                    neighbors.add(edge['source'])
                    # Get source node's info for display
                    source_nodes = [n for n in all_nodes if n['id'] == edge['source']]
                    if source_nodes:
                        source_type = source_nodes[0].get('type', 'Unknown')
                        source_label = source_nodes[0].get('label', edge['source'])
                        neighbor_details_list.append(f"{source_label} ({source_type}) - {edge.get('label', 'connected to')}")
            
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

            return new_elements, tap_output_msg

        # Handle Search Input
        elif trigger_id == 'cytoscape-search-input' and search_value:
            if debug_mode: print(f"Search input: '{search_value}'")
            elements = create_cytoscape_elements('full', search_text=search_value)
            tap_output_msg = dbc.Alert(f"Showing search results for '{search_value}'", color="success") if elements else dbc.Alert("No nodes match your search criteria.", color="warning")
            return elements, tap_output_msg

        # Default: If no specific action matched or search is empty, show full graph
        elements = create_cytoscape_elements('full', search_text=search_value or "")
        tap_output_msg = f"Showing search results for '{search_value}'." if search_value else "Click on a node to see its subgraph details."
        return elements, tap_output_msg

    except Exception as e:
        error_message = f"Error in filter_subgraph callback: {e}"
        print(error_message)
        traceback.print_exc()
        # Return the full graph and an error message
        return create_cytoscape_elements('full'), dbc.Alert(error_message, color="danger")
        
# Timeline Update Callback (Outputs Graph and Table Data)
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

    # Apply type filter
    if selected_types:
        filtered_df = filtered_df[filtered_df['type'].isin(selected_types)]

    # Apply date filter
    if start_date_str and end_date_str:
        try:
            start_date = pd.to_datetime(start_date_str)
            end_date = pd.to_datetime(end_date_str)
            filtered_df = filtered_df[
                (filtered_df['date_parsed'] >= start_date) &
                (filtered_df['date_parsed'] <= end_date)
            ]
        except Exception as e:
            print(f"Date parsing error: {e}")

    fig = create_timeline_figure(filtered_df)
    table_data = filtered_df[['date_str', 'title', 'type', 'location', 'actors_str']].to_dict('records')

    # Handle clickData
    event_details_children = "Click an event on the timeline for details."
    if trigger_id == 'timeline-graph' and click_data:
        try:
            event_title = click_data['points'][0]['hovertext']
            row = timeline_df[timeline_df['title'] == event_title].iloc[0]
            preceded_by = causal_links_df[causal_links_df['target_event'] == event_title]['source_event'].tolist()
            led_to = causal_links_df[causal_links_df['source_event'] == event_title]['target_event'].tolist()

            event_details_children = dbc.Card([
                dbc.CardHeader(html.H5(row['title'])),
                dbc.CardBody([
                    html.P([html.Strong("Date: "), row['date']]),
                    html.P([html.Strong("Location: "), row['location']]),
                    html.P([html.Strong("Type: "), row['type']]),
                    html.P([html.Strong("Actors: "), row['actors_str']]),
                    html.H6("Summary:"), html.P(row['summary']),
                    html.H6("Causal Context:"),
                    html.P([html.Strong("Preceded by: "), ", ".join(preceded_by) or "None"]),
                    html.P([html.Strong("Led to: "), ", ".join(led_to) or "None"]),
                ])
            ])
        except Exception as e:
            print(f"Error extracting event details: {e}")
            event_details_children = dbc.Alert(f"Error loading event details: {str(e)}", color="danger")

    return fig, event_details_children, table_data

# Callback for Actor Tab View Toggle and Details
@app.callback(
    [Output('actor-network-container', 'style'),
     Output('actor-table-container', 'style'),
     Output('actor-details', 'children'),
     Output('actor-network-graph', 'figure')],
    [Input('actor-view-toggle', 'value'),
     Input('actor-network-graph', 'clickData'),
     Input('actors-table', 'active_cell')],
    [State('actors-table', 'data')]
)
def update_actor_view(view_option, network_click, table_cell, table_data):
    network_style = {'display': 'block'} if view_option == 'network' else {'display': 'none'}
    table_style = {'display': 'block'} if view_option == 'table' else {'display': 'none'}
    actor_details_children = "Select an actor from the network or table above."
    actor_name = None
    
    ctx = dash.callback_context
    triggered_id = ctx.triggered[0]['prop_id'].split('.')[0] if ctx.triggered else None

    # Extract clicked actor name from network or table
    try:
        if triggered_id == 'actor-network-graph' and network_click:
            actor_name = network_click['points'][0]['text']
        elif triggered_id == 'actors-table' and table_cell and table_data:
            actor_name = table_data[table_cell['row']]['Name']
    except Exception as e:
        print(f"Error extracting actor: {e}")

    # Build filtered subgraph if actor clicked
    subgraph_fig = create_actor_relationships()
    if view_option == 'network' and actor_name:
        try:
            related_events = set()
            connected_nodes = {actor_name}

            # Find events this actor participated in
            for edge in actor_event_edges + individual_event_edges:
                if edge['source'] == actor_name:
                    related_events.add(edge['target'])

            # Find other actors who also participated in those events
            for edge in actor_event_edges + individual_event_edges:
                if edge['target'] in related_events:
                    connected_nodes.add(edge['source'])

            # Prepare subgraph using NetworkX
            G = nx.Graph()
            for node in all_nodes:
                if node['id'] in connected_nodes or node['id'] in related_events:
                    G.add_node(node['id'], type=node['type'], color=node.get('color', '#ccc'), size=20)

            for edge in all_edges:
                if edge['source'] in G.nodes and edge['target'] in G.nodes:
                    G.add_edge(edge['source'], edge['target'])

            try:
                pos = nx.spring_layout(G, k=0.5, iterations=50)
            except:
                pos = nx.random_layout(G)

            edge_x, edge_y = [], []
            for e in G.edges():
                x0, y0 = pos[e[0]]
                x1, y1 = pos[e[1]]
                edge_x.extend([x0, x1, None])
                edge_y.extend([y0, y1, None])

            node_x, node_y, node_text, node_color, node_size = [], [], [], [], []
            for n in G.nodes(data=True):
                node_id = n[0]
                node_x.append(pos[node_id][0])
                node_y.append(pos[node_id][1])
                node_text.append(node_id)
                node_color.append(n[1].get('color', '#888'))
                node_size.append(n[1].get('size', 20))

            edge_trace = go.Scatter(x=edge_x, y=edge_y, mode='lines', line=dict(width=1, color='#ccc'), hoverinfo='none')
            node_trace = go.Scatter(x=node_x, y=node_y, mode='markers+text', text=node_text, textposition='top center',
                                    marker=dict(size=node_size, color=node_color, line=dict(width=1, color='black')),
                                    hovertext=node_text, hoverinfo='text')
            subgraph_fig = go.Figure(data=[edge_trace, node_trace])
            subgraph_fig.update_layout(
                title=f"Connections of {actor_name}",
                showlegend=False, hovermode='closest',
                margin=dict(b=20, l=5, r=5, t=40),
                xaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
                yaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
                height=700
            )
        except Exception as e:
            print(f"Error creating actor subgraph: {e}")
            traceback.print_exc()

    # Prepare actor detail card
    if actor_name:
        try:
            match_ind = individuals_df[individuals_df['name'] == actor_name]
            match_act = actors_df[actors_df['name'] == actor_name]
            if not match_ind.empty:
                ind = match_ind.iloc[0]
                events = ind['events']
                actor_details_children = dbc.Card([
                    dbc.CardHeader(html.H5(ind['name'])),
                    dbc.CardBody([
                        html.P([html.Strong("Type: "), f"Individual ({ind['role']})"]),
                        html.P([html.Strong("Involvement: "), ind['description']]),
                        html.H6("Events:", style={'marginTop': '10px'}),
                        html.Ul([html.Li(e) for e in events])
                    ])
                ])
            elif not match_act.empty:
                act = match_act.iloc[0]
                events = act['events']
                actor_details_children = dbc.Card([
                    dbc.CardHeader(html.H5(act['name'])),
                    dbc.CardBody([
                        html.P([html.Strong("Type: "), act['type']]),
                        html.P([html.Strong("Role: "), act['role']]),
                        html.H6("Events:", style={'marginTop': '10px'}),
                        html.Ul([html.Li(e) for e in events])
                    ])
                ])
            else:
                actor_details_children = dbc.Alert(f"No details found for {actor_name}", color="warning")
        except Exception as e:
            print(f"Error creating actor details: {e}")
            actor_details_children = dbc.Alert(f"Error loading actor details: {str(e)}", color="danger")

    return network_style, table_style, actor_details_children, subgraph_fig

# Callback to reset causal layout
@app.callback(
    Output('cytoscape-causal-graph', 'layout'),
    Input('reset-causal-layout', 'n_clicks'),
    prevent_initial_call=True
)
def reset_causal_layout(n_clicks):
    return {
        'name': 'breadthfirst',
        'roots': '[id = "Ukraine Drops EU Deal; Protests Begin (Euromaidan)"]',
        'spacingFactor': 1.5,
        'animate': False
    }

# ------------------------------------------------------------------------------
# RUN THE APPLICATION
# ------------------------------------------------------------------------------
if __name__ == '__main__':
    print("Attempting to start Dash server...")
    print(f"Current Working Directory: {os.getcwd()}")
    # Run Dash server
    app.run(debug=True, host='0.0.0.0', port=8052) # Changed port to 8052