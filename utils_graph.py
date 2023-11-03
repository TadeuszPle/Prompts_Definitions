import csv
import json
from typing import Dict, Generator, List, Tuple

import networkx as nx

candidates_path: str = "/data3/tplesniak/wsd-generative/storage/plwn_lemma_candidates.json"


def read_csv(path: str):
    with open(path) as csvfile:
        reader = csv.reader(csvfile)
        yield from reader


def read_jsonl(path: str):
    with open(path) as jsonlfile:
        for line in jsonlfile:
            yield json.loads(line)


def get_definitions(path: str = "/data3/tplesniak/wsd-generative/storage/plwn_definitions.jsonl") -> Dict[str, str]:
    return {line["pl_sense"]: line["text"] for line in read_jsonl(path)}


def get_senses(path: str = "/data3/tplesniak/wsd-generative/storage/senses.csv") -> Dict[str, str]:
    return {line[0]: line[1] for line in read_csv(path)}


def get_no_defs(senses, definitions) -> List[str]:
    return [ind for ind, sen in senses.items() if sen not in definitions]


def get_relacje(path: str, encoding: str = "utf-8"):
    with open(path, encoding=encoding) as f:
        for line in f:
            data = line.replace("\n", "").split("\t")
            yield data


def get_graph_ind(relations, senses) -> Generator[Tuple[str, str, Dict[str, str]], None, None]:
    for r in relations:
        yield (senses[r[0]], senses[r[1]], {"type": r[2]})


def ind_in_senses(relations, senses):
    for r in relations:
        if r[0] not in senses or r[1] not in senses:
            continue
        else:
            yield r


def populate_graph(Gr: nx.Graph, senses: Dict[str, str]) -> None:
    # populates the Graph but only with the id's that hava a sense in senses
    rels_path1 = "relacje-jednostek/relacje-p1-fixed.txt"
    rels_path2 = "relacje-jednostek/relacje-p2-fixed.txt"
    for path in [rels_path1, rels_path2]:
        rels = get_relacje(path)
        rels_in_sens = ind_in_senses(rels, senses)
        connections = get_graph_ind(rels_in_sens, senses)
        Gr.add_edges_from(connections)
        remove_duplicate_nodes(Gr)


def generate_prompt(word: str, G: nx.Graph, definitions) -> str:
    word_limit = 30
    out_subprompt_limit = 10
    in_subprompt_limit = 8
    relations_out = G[word]
    relations_in = G.in_edges(word)

    types_in = [con["type"] for n1, n2 in relations_in for con in G[n1][n2].values()]
    senses_in = [n1 for n1, n2 in relations_in]

    types_out = [con["type"] for word2 in relations_out for con in relations_out[word2].values()]
    sens_out = [cons for cons in relations_out for _ in relations_out[cons]]

    # grouping by relation type

    def plwn_to_pl(text: str) -> str:
        # this maybe should be regex?
        return text[:-4].replace("_", " ")

    def get_subprompt(typ, sens) -> str:
        definition = definitions[sens] if sens in definitions else None
        prefix = f"typ relacji: {typ}, słowo: {plwn_to_pl(sens)},"
        return prefix + definition if definition else prefix + " brak definicji"

    start = f"Mam słowo '{plwn_to_pl(word)}' dla którego nie mam definicji, ale mam relacje, które łączą to słowo z innymi. "
    middle = (
        f"\nPodaj definicję mojego słowa. Weź pod uwagę podane relacje i podaj definicję związaną z poodanymi relacjami. "
        f"Postaraj się użyć nie więcej niż {word_limit} słów. "
        "W definicji nie powinno być słowa, które jest definiowane. "
        "Definicja powinna mieć formę <słowo> : <definicja>\n"
    )
    subprompts_out = "Relacje tego słowa z innymi słowami:\n" + "\n".join(
        [get_subprompt(t, s) for t, s in zip(types_out, sens_out)][:out_subprompt_limit]
    )
    subprompts_in = "\nRelacje innych słów z tym słowem:\n" + "\n".join(
        [get_subprompt(t, s) for t, s in zip(types_in, senses_in) if (t, s) not in zip(types_out, sens_out)][
            :in_subprompt_limit
        ]
    )
    return start + middle + subprompts_out + subprompts_in + "\n"


def remove_duplicate_nodes(H: nx.MultiDiGraph):
    for node in H.nodes():
        for adj in H[node]:
            curr_types = set()
            for k, t in list(H[node][adj].items()):
                if t["type"] not in curr_types:
                    curr_types.add(t["type"])
                else:
                    H.remove_edge(node, adj, key=k)


def count_no_def(G: nx.Graph, definitions: Dict[str, str]) -> int:
    return sum([1 for n in G.nodes() if n not in definitions])


def count_no_def_big_degree(G: nx.Graph, definitions: Dict[str, str]):
    return sum([1 for n in G.nodes() if G.degree[n] > 1 and n not in definitions])


def type_in_connections(cons: Dict, typ: str) -> int:
    for k, t in cons.items():
        if t["type"] == typ:
            return True
    return False


def get_connection_with_type(G: nx.Graph, typ: str):
    nodes = []
    for n1, n2 in G.edges():
        if type_in_connections(G[n1][n2], typ):
            nodes.append((n1, n2))
    return nodes


def print_node_connections(node: str, G) -> None:
    print(node)
    for n in G[node]:
        print(G[node][n], node)


def hiper_and_hipo(G: nx.Graph):
    both = []
    for (n1, n2) in G.edges():
        if type_in_connections(G[n1][n2], "hiperonimia") and type_in_connections(G[n1][n2], "hiponimia"):
            both.append((n1, n2))
    return both


def hiper_and_hipo2(G: nx.Graph):
    both = []
    for n1 in G.nodes():
        for n2 in G[n1]:
            if type_in_connections(G[n1][n2], "hiperonimia") and type_in_connections(G[n1][n2], "hiponimia"):
                both.append((n1, n2))
    return both


def count_connection_types(G):
    count = {}
    for _, _, data in G.edges(data=True):
        if data["type"] not in count:
            count[data["type"]] = 1
        else:
            count[data["type"]] += 1
    return count
