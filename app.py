from flask import Flask, request
from flask_sqlalchemy import SQLAlchemy

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///data.db'
db = SQLAlchemy(app)

@app.cli.command("init-db")
def init_db():
    db.create_all()
    print("Database Initialized")

class Cafe(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), unique=True, nullable=False)
    price = db.Column(db.Numeric(10, 2), nullable=False)
    description = db.Column(db.String(120))

    def __repr__(self):
        return f"{self.name} - {self.price} - {self.description}"

@app.route('/')
def index():
    return 'Hello!'

@app.route('/cafe')
def get_cafe():
    cafe = Cafe.query.all()
    output = []
    for item in cafe:
        cafe_item = {'name': item.name, 'price': item.price, 'description': item.description}

        output.append(cafe_item)

    return {"cafe": output}

@app.route('/cafe/<id>')
def get_item(id):
    item = Cafe.query.get_or_404(id)
    return {"name": item.name, "price": item.price, "description": item.description}
    
@app.route('/cafe', methods=['POST'])
def add_item():
    item = Cafe(name=request.json['name'], price=request.json['price'], description=request.json['description'])
    db.session.add(item)
    db.session.commit()
    return {'id': item.id}

@app.route('/cafe/<id>', methods=['DELETE'])
def delete_item(id):
    item = Cafe.query.get(id)
    if item is None:
        return {"error": "The Item Not found"}
    db.session.delete(item)
    db.session.commit()
    return {"Message": "The Item id Deleted successfully"}

@app.route('/cafe/<id>', methods=['PUT'])
def update_item(id):
    item = Cafe.query.get(id)
    if item is None:
        return {"error": "The item Not Found!"}, 404
    
    item.name = request.json['name']
    item.price = request.json['price']
    item.description = request.json['description']

    db.session.commit()
    return {"Message": "The item has been updated successfully"}

if __name__ == "__main__":
    app.run(debug=True)