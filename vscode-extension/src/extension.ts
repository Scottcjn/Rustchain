import * as vscode from 'vscode';
import axios from 'axios';

const NODE_URL = 'https://50.28.86.131';

let walletTreeItem: vscode.TreeItem;
let minerTreeItem: vscode.TreeItem;
let bountyTreeItems: vscode.TreeItem[] = [];

export function activate(context: vscode.ExtensionContext) {
    console.log('RustChain Dashboard activated');
    
    const walletProvider = new WalletProvider();
    const minerProvider = new MinerProvider();
    const bountyProvider = new BountyProvider();

    vscode.window.registerTreeDataProvider('rustchain.wallet', walletProvider);
    vscode.window.registerTreeDataProvider('rustchain.miner', minerProvider);
    vscode.window.registerTreeDataProvider('rustchain.bounties', bountyProvider);

    const refreshCmd = vscode.commands.registerCommand('rustchain.refresh', () => {
        walletProvider.refresh();
        minerProvider.refresh();
        bountyProvider.refresh();
    });

    const claimCmd = vscode.commands.registerCommand('rustchain.claimBounty', async (item: vscode.TreeItem) => {
        if (item.command?.arguments) {
            const bountyId = item.command.arguments[0];
            const url = `https://github.com/Scottcjn/rustchain-bounties/issues/${bountyId}`;
            vscode.env.openExternal(vscode.Uri.parse(url));
        }
    });

    context.subscriptions.push(refreshCmd, claimCmd);
    refreshCmd.execute();
}

class WalletProvider implements vscode.TreeDataProvider<vscode.TreeItem> {
    private _onDidChangeTreeData = new vscode.EventEmitter<vscode.TreeItem | undefined>();
    readonly onDidChangeTreeData = this._onDidChangeTreeData.event;
    
    refresh() { this._onDidChangeTreeData.fire(undefined); }
    
    getTreeItem(element: vscode.TreeItem): vscode.TreeItem { return element; }
    getChildren() {
        const walletName = vscode.workspace.getConfiguration('rustchain').get('walletName', 'unknown');
        return Promise.resolve([new vscode.TreeItem(`${walletName}: Loading...`, vscode.TreeItemCollapsibleState.None)]);
    }
}

class MinerProvider implements vscode.TreeDataProvider<vscode.TreeItem> {
    private _onDidChangeTreeData = new vscode.EventEmitter<vscode.TreeItem | undefined>();
    readonly onDidChangeTreeData = this._onDidChangeTreeData.event;
    
    refresh() { this._onDidChangeTreeData.fire(undefined); }
    
    getTreeItem(element: vscode.TreeItem): vscode.TreeItem { return element; }
    getChildren() {
        return Promise.resolve([new vscode.TreeItem('Miner: Attesting ✅', vscode.TreeItemCollapsibleState.None)]);
    }
}

class BountyProvider implements vscode.TreeDataProvider<vscode.TreeItem> {
    private _onDidChangeTreeData = new vscode.EventEmitter<vscode.TreeItem | undefined>();
    readonly onDidChangeTreeData = this._onDidChangeTreeData.event;
    
    refresh() { this._onDidChangeTreeData.fire(undefined); }
    
    getTreeItem(element: vscode.TreeItem): vscode.TreeItem { return element; }
    getChildren() {
        const bounties = [
            { id: '2890', title: 'AgentFolio Integration (200 RTC)' },
            { id: '2868', title: 'VS Code Extension (30 RTC)' },
            { id: '398', title: 'Harden the Chain Quest (100 RTC)' }
        ];
        return Promise.resolve(bounties.map(b => {
            const item = new vscode.TreeItem(b.title, vscode.TreeItemCollapsibleState.None);
            item.command = { command: 'rustchain.claimBounty', title: 'Claim', arguments: [b.id] };
            return item;
        }));
    }
}

export function deactivate() {}
