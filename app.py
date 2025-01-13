from flask import Flask, render_template, request, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
import re
import requests
import singularize
from bs4 import BeautifulSoup

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///cache.db'
db = SQLAlchemy(app)

class Item(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(80), unique=True, nullable=False)
    quantidade = db.Column(db.Integer, default=0)
    valor = db.Column(db.Float, nullable=False)

    def __repr__(self):
        return f'<Item {self.nome}>'

def normalizar_item(item):
    item = item.strip().capitalize()
    item = singularize.singularize(item)
    if item.split(" ") and item.endswith("s"):
        item = item[:-1]
    return item

def recuperar_valores_itens():
    url = "https://wiki.pokexgames.com/index.php/Nightmare_Merchant_(Resistance)"
    response = requests.get(url)
    soup = BeautifulSoup(response.content, 'html.parser')
    
    tabelas = soup.find_all('table', {'class': 'wikitable'})
    if len(tabelas) >= 8:
        tabela = tabelas[7]  # Seleciona a oitava tabela
        linhas = tabela.find_all('tr')
        for linha in linhas[1:]:  # Pular o cabeçalho
            colunas = linha.find_all('td')
            if len(colunas) >= 9:
                for i in [1, 4, 7]:  # Índices das colunas de itens
                    item_coluna = colunas[i]
                    valor_coluna = colunas[i + 1]
                    
                    item_nome = normalizar_item(item_coluna.get_text(strip=True))
                    valor = valor_coluna.get_text(strip=True).replace('$', '').replace(',', '').replace(' ', '')
                    try:
                        valor = float(valor)
                        item = Item.query.filter_by(nome=item_nome).first()
                        if item:
                            item.valor = valor
                        else:
                            new_item = Item(nome=item_nome, valor=valor)
                            db.session.add(new_item)
                    except ValueError:
                        continue
        db.session.commit()

def analisar_entrada(entrada):
    padrao = r'(\d+)\s([\w\s]+?)(?=,| e|$)'
    itens = re.findall(padrao, entrada)
    itens_sem_preco = []
    for quantidade, item_nome in itens:
        item_nome = normalizar_item(item_nome)
        quantidade = int(quantidade)
        if quantidade == 0:
            continue
        item = Item.query.filter_by(nome=item_nome).first()
        if item:
            item.quantidade += quantidade
        else:
            new_item = Item(nome=item_nome, quantidade=quantidade, valor=0.0)
            db.session.add(new_item)
            itens_sem_preco.append(new_item)
    db.session.commit()
    if itens_sem_preco:
        return True
    return False

def formatar_valor(valor):
    valor = int(valor)  # Ensure the value is an integer
    if valor >= 1_000_000:
        return f'{valor // 1_000_000}KK'
    elif valor >= 1_000:
        return f'{valor // 1_000}K'
    else:
        return str(valor)

def formatar_valor_total(valor):
    if valor >= 1_000_000:
        return f'{valor / 1_000_000:.2f}KK'
    elif valor >= 1_000:
        return f'{valor / 1_000:.2f}K'
    else:
        return f'{valor:.2f}'

@app.route('/price', methods=['GET', 'POST'])
def price():
    if request.method == 'POST':
        for item_nome, valor in request.form.items():
            item = Item.query.filter_by(nome=item_nome).first()
            if item:
                item.valor = float(valor)
        db.session.commit()
        return redirect(url_for('index'))
    else:
        itens_sem_preco = Item.query.filter_by(valor=0.0).all()
        return render_template('price.html', itens=itens_sem_preco)

@app.route('/')
def index():
    if Item.query.count() == 0:
        recuperar_valores_itens()
    itens = Item.query.all()
    total_value = sum(item.quantidade * item.valor for item in itens if item.quantidade > 0)
    total_value_formatado = formatar_valor_total(total_value)
    return render_template('index.html', cache=itens, total_value=total_value_formatado, formatar_valor=formatar_valor)

@app.route('/add', methods=['POST'])
def add():
    entrada = request.form['entrada']
    if analisar_entrada(entrada):
        return redirect(url_for('price'))
    else:
        return redirect(url_for('index'))

@app.route('/clear', methods=['POST'])
def clear():
    db.session.query(Item).delete()
    db.session.commit()
    return redirect(url_for('index'))

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)